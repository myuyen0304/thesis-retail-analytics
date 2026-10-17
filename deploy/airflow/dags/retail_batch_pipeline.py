"""Airflow điều phối các stage; SQL nghiệp vụ vẫn nằm trong dbt."""
from datetime import timedelta
import hashlib
import os
import subprocess

import pendulum
from airflow.sdk import DAG, Param, get_current_context, task
from airflow.exceptions import AirflowFailException


def command(stage, context):
    run_id = hashlib.sha256(context['run_id'].encode()).hexdigest()[:24]
    params = context['params']
    args = ['/opt/pipeline/bin/python', '-m', 'scripts.pipeline.cli', stage,
            '--run-id', run_id, '--target', params['target'], '--root', 'warehouse/pipeline/docker']
    if params.get('snapshot_id'):
        args += ['--snapshot-id', params['snapshot_id']]
    if params.get('force'):
        args.append('--force')
    return args


with DAG(
    dag_id='retail_batch_pipeline',
    start_date=pendulum.datetime(2026, 10, 11, tz='Asia/Ho_Chi_Minh'),
    schedule='0 8 * * *' if os.getenv('RETAIL_PIPELINE_SCHEDULE_ENABLED') == 'true' else None,
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    dagrun_timeout=timedelta(hours=2),
    default_args={'retries': 2, 'retry_delay': timedelta(minutes=2),
                  'execution_timeout': timedelta(minutes=65)},
    params={'target': Param('duckdb', enum=['duckdb', 'databricks']),
            'snapshot_id': Param(None, type=['null', 'string'], pattern='^[a-f0-9]{12}$'),
            'force': Param(False, type='boolean')},
    tags=['retail', 'batch'],
) as dag:
    @task
    def stage(name):
        result = subprocess.run(command(name, get_current_context()), cwd='/opt/retail', timeout=3800)
        if result.returncode == 2:
            raise AirflowFailException(f'{name}: sai hợp đồng/quality gate; xem console.log và failure.json')
        if result.returncode:
            raise RuntimeError(f'{name}: lỗi tạm thời, exit={result.returncode}')

    prepare = stage.override(task_id='prepare_snapshot')('prepare')
    build = stage.override(task_id='ingest_and_dbt_build')('build')
    validate = stage.override(task_id='quality_and_reader_gate')('validate')
    publish = stage.override(task_id='publish_release')('publish')
    prepare >> build >> validate >> publish
