import logging

from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from typing import Any, List, Optional


def python_type_to_bq_type(py_val: Any) -> str:
    """Map a JSON-compatible Python value to a BigQuery type."""
    # bool must be checked before int because bool is a subclass of int
    if isinstance(py_val, bool):
        return "BOOLEAN"
    type_map = {
        str: "STRING",
        int: "INT64",
        float: "FLOAT64",
    }
    return type_map.get(type(py_val), "STRING")  # default to STRING


def pydict_to_bqschema_recursive(data: dict) -> List[bigquery.SchemaField]:
    """
    Generate a BigQuery schema from a nested Python dict.
    All fields are NULLABLE unless they are arrays, which are REPEATED.
    """
    schema: List[bigquery.SchemaField] = []

    for key, value in data.items():
        if isinstance(value, dict):
            # Nested RECORD field (always NULLABLE)
            nested_fields = pydict_to_bqschema_recursive(value)
            schema.append(
                bigquery.SchemaField(
                    name=key,
                    field_type="RECORD",
                    mode="NULLABLE",
                    fields=nested_fields,
                )
            )

        elif isinstance(value, list):
            # Arrays are REPEATED; infer element type from first item when available.
            if not value:
                # Default to REPEATED STRING for empty lists
                schema.append(
                    bigquery.SchemaField(
                        name=key,
                        field_type="STRING",
                        mode="REPEATED",
                    )
                )
            else:
                first = value[0]
                if isinstance(first, dict):
                    nested_fields = pydict_to_bqschema_recursive(first)
                    schema.append(
                        bigquery.SchemaField(
                            name=key,
                            field_type="RECORD",
                            mode="REPEATED",
                            fields=nested_fields,
                        )
                    )
                else:
                    bq_type = python_type_to_bq_type(first)
                    schema.append(
                        bigquery.SchemaField(
                            name=key,
                            field_type=bq_type,
                            mode="REPEATED",
                        )
                    )

        else:
            # Scalar field (always NULLABLE)
            bq_type = python_type_to_bq_type(value)
            schema.append(
                bigquery.SchemaField(
                    name=key,
                    field_type=bq_type,
                    mode="NULLABLE",
                )
            )

    return schema


def pydict_to_bqschema(data: dict, sync_timestamp_column: str = "AsteriskSyncDate") -> List[bigquery.SchemaField]:
    """
    Generate a BigQuery schema from a nested Python dict.
    Appends a REQUIRED timestamp field at the end.
    """
    schema = pydict_to_bqschema_recursive(data)

    schema.append(
        bigquery.SchemaField(
            name=sync_timestamp_column,
            field_type="TIMESTAMP",
            mode="REQUIRED",
            description="Row ingestion timestamp (defaults to CURRENT_TIMESTAMP())",
        )
    )

    return schema


def does_bq_table_exist(bq_client, table_ref: str):
    try:
        bq_client.get_table(table_ref)
        return True
    except NotFound:
        return False


def make_bq_table(
    bq_client,
    table_ref: str,
    schema_dict: dict,
    sync_timestamp_column: str = "AsteriskSyncDate",
) -> List[bigquery.SchemaField]:
    """
    Create a BigQuery table from a schema dict. Returns the generated schema.
    No-ops if the table already exists.
    """
    try:
        bq_client.get_table(table_ref)
        return []
    except NotFound:
        pass

    schema = pydict_to_bqschema(schema_dict, sync_timestamp_column=sync_timestamp_column)

    table = bigquery.Table(table_ref, schema=schema)
    bq_client.create_table(table)

    alter_sql = f"""
    ALTER TABLE `{table_ref}`
    ALTER COLUMN {sync_timestamp_column}
    SET DEFAULT CURRENT_TIMESTAMP();
    """

    bq_client.query(alter_sql)

    return schema


# Gets only the latest relevant row for each PK based on the sync timestamp column
def get_latest_bq_rows(
    bq_client,
    table_ref: str,
    pk_name: str,
    pk_list: Optional[list[int]] = None,
    sync_timestamp_column: str = "AsteriskSyncDate",
) -> list[dict]:
    # If table does not exist, return empty list
    if not does_bq_table_exist(bq_client, table_ref):
        return []

    where_clauses: list[str] = []
    if pk_list:
        where_clauses.append(f"{pk_name} IN UNNEST(@pk_list)")

    where_sql = f"WHERE {' OR '.join(where_clauses)}" if where_clauses else ""

    query = f"""
    SELECT * EXCEPT({sync_timestamp_column})
    FROM `{table_ref}`
    {where_sql}
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY {pk_name}
        ORDER BY {sync_timestamp_column} DESC
    ) = 1
    """

    params = []
    if pk_list:
        pk_type = python_type_to_bq_type(pk_list[0])
        params.append(bigquery.ArrayQueryParameter("pk_list", pk_type, pk_list))

    job_config = bigquery.QueryJobConfig(query_parameters=params) if params else None
    results = bq_client.query(query, job_config=job_config).result()

    data = [dict(row) for row in results]

    return data


class SchemaDriftError(Exception):
    pass


def _bq_field_names(schema, prefix=""):
    """Recursively collect all field names from a BQ schema, using dot notation for nested fields."""
    names = set()
    for field in schema:
        full_name = f"{prefix}{field.name}"
        names.add(full_name)
        if field.field_type == "RECORD" and field.fields:
            names |= _bq_field_names(field.fields, prefix=f"{full_name}.")
    return names


def _data_field_names(record, prefix=""):
    """Recursively collect all field names from a data dict, using dot notation for nested fields."""
    names = set()
    for key, value in record.items():
        full_name = f"{prefix}{key}"
        names.add(full_name)
        if isinstance(value, dict):
            names |= _data_field_names(value, prefix=f"{full_name}.")
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            names |= _data_field_names(value[0], prefix=f"{full_name}.")
    return names


def _get_sample_value(dotted_field, data):
    """Walk into data records to find the first non-None sample value for a dotted field path."""
    parts = dotted_field.split(".")
    for record in data:
        val = record
        for part in parts:
            if isinstance(val, dict) and part in val:
                val = val[part]
            else:
                val = None
                break
        if val is not None:
            return val
    return ""  # default to STRING


def _dict_to_struct_type(d):
    """Convert a sample dict value to a BQ STRUCT type string, e.g. STRUCT<name STRING, age INT64>."""
    fields = []
    for key, value in d.items():
        if isinstance(value, dict):
            fields.append(f"{key} {_dict_to_struct_type(value)}")
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                fields.append(f"{key} ARRAY<{_dict_to_struct_type(value[0])}>")
            else:
                elem_type = python_type_to_bq_type(value[0]) if value else "STRING"
                fields.append(f"{key} ARRAY<{elem_type}>")
        else:
            fields.append(f"{key} {python_type_to_bq_type(value)}")
    return f"STRUCT<{', '.join(fields)}>"


def _suggest_alter(table_ref, field_name, sample_value):
    """Generate an ALTER TABLE statement for a new field, handling nested STRUCT types."""
    if isinstance(sample_value, dict):
        bq_type = _dict_to_struct_type(sample_value)
    else:
        bq_type = python_type_to_bq_type(sample_value)
    return f"ALTER TABLE `{table_ref}` ADD COLUMN {field_name} {bq_type};"


def check_schema_drift(bq_client, table_ref, data, sync_timestamp_column="AsteriskSyncDate"):
    """
    Compare data fields against the BQ table schema.
    Raises SchemaDriftError with actionable ALTER TABLE statements if new fields are found.
    """
    table = bq_client.get_table(table_ref)
    bq_fields = _bq_field_names(table.schema) - {sync_timestamp_column}

    # Scan all records to find every field name present in the data
    all_data_fields = set()
    for record in data:
        all_data_fields |= _data_field_names(record)

    new_fields = all_data_fields - bq_fields
    if not new_fields:
        return

    # Only generate ALTER statements for "root" new fields — those whose parent
    # either is top-level or already exists in the BQ schema.  Children of new
    # RECORD fields are covered by the parent's STRUCT definition.
    root_new_fields = set()
    for field in new_fields:
        parts = field.split(".")
        if len(parts) == 1:
            root_new_fields.add(field)
        else:
            parent = ".".join(parts[:-1])
            if parent in bq_fields:
                root_new_fields.add(field)
            # else: parent is also new, handled by the parent's STRUCT ALTER

    alter_statements = []
    for field in sorted(root_new_fields):
        sample = _get_sample_value(field, data)
        alter_statements.append(_suggest_alter(table_ref, field, sample))

    msg = (
        f"Schema drift detected on {table_ref}: new fields from API: {', '.join(sorted(new_fields))}.\n"
        f"Run the following to update the table:\n\n" + "\n".join(alter_statements)
    )
    logging.error(msg)
    raise SchemaDriftError(msg)
