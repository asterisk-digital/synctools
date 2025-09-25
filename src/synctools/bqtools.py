from pathlib import Path

from google.cloud import bigquery
from typing import Any, List


def python_type_to_bq_type(py_val: Any) -> str:
    """Map a JSON-compatible Python value to a BigQuery type."""
    type_map = {
        str: "STRING",
        int: "INT64",
        float: "FLOAT64",
        bool: "BOOLEAN",
    }
    return type_map.get(type(py_val), "STRING")  # default to STRING


def pydict_to_bqschema_recursive(data: dict, pk_field: str | None = None) -> List[bigquery.SchemaField]:
    """
    Generate a BigQuery schema from a nested Python dict
    """
    schema = []

    for key, value in data.items():
        if isinstance(value, dict):
            # Nested RECORD field
            nested_fields = pydict_to_bqschema_recursive(value)
            field_mode = "REQUIRED" if pk_field and key == pk_field else "NULLABLE"
            schema.append(bigquery.SchemaField(name=key, field_type="RECORD", mode=field_mode, fields=nested_fields))
        elif isinstance(value, list):
            if not value:
                # Default to REPEATED STRING for empty lists
                schema.append(bigquery.SchemaField(name=key, field_type="STRING", mode="REPEATED"))
            else:
                first = value[0]
                if isinstance(first, dict):
                    nested_fields = pydict_to_bqschema_recursive(first)
                    schema.append(
                        bigquery.SchemaField(name=key, field_type="RECORD", mode="REPEATED", fields=nested_fields)
                    )
                else:
                    bq_type = python_type_to_bq_type(first)
                    schema.append(bigquery.SchemaField(name=key, field_type=bq_type, mode="REPEATED"))
        else:
            bq_type = python_type_to_bq_type(value)
            field_mode = "REQUIRED" if pk_field and key == pk_field else "NULLABLE"
            schema.append(bigquery.SchemaField(name=key, field_type=bq_type, mode=field_mode))

    return schema

def pydict_to_bqschema(data: dict, pk_field: str | None = None) -> List[bigquery.SchemaField]:
    """
    Generate a BigQuery schema from a nested Python dict or list of dicts.
    :param data:
    :param pk_field:
    :return:
    """

    schema = pydict_to_bqschema_recursive(data, pk_field)

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


def make_bq_table(bq_client, bq_project, bq_dataset, bq_table: str, template_dict: dict):
    # Short-circuit if the BQ table already exists
    table_ref = f"{bq_project}.{bq_dataset}.{bq_table}"
    try:
        bq_client.get_table(table_ref)
        return
    except Exception as e:
        # If it's not a NotFound error, raise it
        if "Not found" not in str(e):
            raise

    schema = pydict_to_bqschema(template_dict, pk_field=None)

    # We want this in source control too
    with open(f"bqschema_{bq_table}.txt", "w") as f:
        for field in schema:
            f.write(str(field) + "\n")

    # Create BQ table
    table_id = f"{bq_project}.{bq_dataset}.{bq_table}"
    table = bigquery.Table(table_id, schema=schema)
    table = bq_client.create_table(table)

    # Run ALTER TABLE to set default on AsteriskSyncDate
    alter_sql = f"""
    ALTER TABLE `{table_id}`
    ALTER COLUMN AsteriskSyncDate
    SET DEFAULT CURRENT_TIMESTAMP();
    """

    bq_client.query(alter_sql)
