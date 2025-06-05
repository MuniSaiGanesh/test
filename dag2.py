from airflow import models
from airflow.contrib.operators.bigquery_to_gcs import BigQueryToCloudStorageOperator
from airflow.operators.python_operator import PythonOperator
from airflow.contrib.operators.gcs_list_operator import GoogleCloudStorageListOperator
from airflow.utils.dates import days_ago
from datetime import timedelta

# ✅ Function to merge GCS shards into a single CSV file
def recursive_compose(bucket, final_object, **kwargs):
    from google.cloud import storage

    ti = kwargs['ti']
    object_names = ti.xcom_pull(task_ids='list_csv_shards')

    if not object_names:
        raise ValueError("No CSV shards found to merge.")

    client = storage.Client()
    temp_prefix = 'exports/thoughtspot_table/temp_merge_'
    current_objects = object_names
    step = 0

    # Handle >32 file limit with batching
    while len(current_objects) > 32:
        next_round = []
        for i in range(0, len(current_objects), 32):
            group = current_objects[i:i + 32]
            composed_name = f'{temp_prefix}{step}_{i//32}.csv'
            client.bucket(bucket).blob(composed_name).compose(
                [client.bucket(bucket).blob(name) for name in group]
            )
            next_round.append(composed_name)
        current_objects = next_round
        step += 1

    # Final merge to single file
    client.bucket(bucket).blob(final_object).compose(
        [client.bucket(bucket).blob(name) for name in current_objects]
    )

# ✅ DAG Configuration
PROJECT_ID = 'networkperformanceassessment'
BQ_TABLE = 'networkperformanceassessment.Ts_dataset.thoughtspot_table'
GCS_BUCKET = 'ug2_poc'  # Your working bucket with access
EXPORT_PREFIX = 'exports/thoughtspot_table'
SHARD_PATTERN = f'{EXPORT_PREFIX}/data-*.csv'
FINAL_CSV_NAME = f'{EXPORT_PREFIX}/thoughtspot_table_full.csv'

default_args = {
    'start_date': days_ago(1),
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

with models.DAG(
    dag_id='bq_export_merge_single_csv_with_workaround',
    schedule_interval=None,
    default_args=default_args,
    catchup=False,
    description='Export BQ table to CSV shards in own bucket and merge to a single CSV',
    tags=['bq', 'gcs', 'csv', 'merge'],
) as dag:

    # Export table to sharded CSVs
    export_to_csv = BigQueryToCloudStorageOperator(
        task_id='export_sharded_csv',
        source_project_dataset_table=BQ_TABLE,
        destination_cloud_storage_uris=[f'gs://{GCS_BUCKET}/{SHARD_PATTERN}'],
        export_format='CSV',
        field_delimiter=',',
        print_header=True,
        compression='NONE',
    )

    # List shard objects in GCS
    list_shards = GoogleCloudStorageListOperator(
        task_id='list_csv_shards',
        bucket=GCS_BUCKET,
        prefix=EXPORT_PREFIX + '/data-',
    )

    # Merge all shards into a single CSV file
    merge_csv = PythonOperator(
        task_id='merge_csv_shards',
        python_callable=recursive_compose,
        provide_context=True,
        op_kwargs={
            'bucket': GCS_BUCKET,
            'final_object': FINAL_CSV_NAME,
        },
    )

    export_to_csv >> list_shards >> merge_csv
