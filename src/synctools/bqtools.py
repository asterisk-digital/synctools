from google.cloud import bigquery
from typing import Any, List, Optional


def python_type_to_bq_type(py_val: Any) -> str:
    """Map a JSON-compatible Python value to a BigQuery type."""
    type_map = {
        str: "STRING",
        int: "INT64",
        float: "FLOAT64",
        bool: "BOOLEAN",
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


def pydict_to_bqschema(data: dict) -> List[bigquery.SchemaField]:
    """
    Generate a BigQuery schema from a nested Python dict.
    Appends a REQUIRED AsteriskSyncDate TIMESTAMP field at the end.
    """
    schema = pydict_to_bqschema_recursive(data)

    # Add AsteriskSyncDate at the end
    schema.append(
        bigquery.SchemaField(
            name="AsteriskSyncDate",
            field_type="TIMESTAMP",
            mode="REQUIRED",
            description="Row ingestion timestamp (defaults to CURRENT_TIMESTAMP())",
        )
    )

    return schema


def does_bq_table_exist(bq_client, bq_project: str, bq_dataset: str, bq_table: str):
    table_ref = f"{bq_project}.{bq_dataset}.{bq_table}"

    try:
        bq_client.get_table(table_ref)
        return True
    except Exception as e:
        if "Not found" not in str(e):
            raise
        return False


def make_bq_table(bq_client, bq_project, bq_dataset, bq_table: str, schema_dict: dict):
    # Short-circuit if the BQ table already exists
    table_ref = f"{bq_project}.{bq_dataset}.{bq_table}"
    try:
        bq_client.get_table(table_ref)
        return
    except Exception as e:
        # If it's not a NotFound error, raise it
        if "Not found" not in str(e):
            raise

    schema = pydict_to_bqschema(schema_dict)

    # We want this in source control too
    with open(f"bqschema_{bq_table}.txt", "w") as f:
        for field in schema:
            f.write(str(field) + "\n")

    # Create BQ table
    table_ref = f"{bq_project}.{bq_dataset}.{bq_table}"
    table = bigquery.Table(table_ref, schema=schema)
    table = bq_client.create_table(table)

    # Run ALTER TABLE to set default on AsteriskSyncDate
    alter_sql = f"""
    ALTER TABLE `{table_ref}`
    ALTER COLUMN AsteriskSyncDate
    SET DEFAULT CURRENT_TIMESTAMP();
    """

    bq_client.query(alter_sql)


# Gets only the latest relevant row for each PK based on AsteriskSyncDate
def get_latest_bq_rows(
    bq_client,
    bq_project: str,
    bq_dataset: str,
    bq_table: str,
    pk_name: str,
    pk_list: Optional[list[int]] = None,
) -> list[dict]:
    table_ref = f"{bq_project}.{bq_dataset}.{bq_table}"

    # If table does not exist, return empty list
    if not does_bq_table_exist(bq_client, bq_project, bq_dataset, bq_table):
        return []

    where_clauses: list[str] = []
    if pk_list:
        where_clauses.append(f"{pk_name} IN UNNEST(@pk_list)")

    where_sql = f"WHERE {' OR '.join(where_clauses)}" if where_clauses else ""

    query = f"""
    SELECT * EXCEPT(AsteriskSyncDate)
    FROM `{table_ref}`
    {where_sql}
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY {pk_name}
        ORDER BY AsteriskSyncDate DESC
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
