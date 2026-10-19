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
    # Lịch 08:00 không truyền được conf, nên target mặc định (cả lịch lẫn trigger tay không ghi target) đọc từ
    # .env.airflow.local; không đặt thì giữ duckdb. PM chốt 2026-10-19: máy chạy demo đặt databricks để lịch chạy production.
    params={'target': Param(os.getenv('RETAIL_PIPELINE_DEFAULT_TARGET', 'duckdb'), enum=['duckdb', 'databricks']),
            'snapshot_id': Param(None, type=['null', 'string'], pattern='^[a-f0-9]{12}$'),
            'force': Param(False, type='boolean')},
    tags=['retail', 'batch'],
) as dag:
    @task
    def stage(name, timeout_s=3800):
        # timeout_s luôn dưới execution_timeout của chính task (65 phút mặc định): subprocess tự dừng CLI trước khi
        # Airflow cắt task, nên không còn tiến trình con giữ writer.lock khi retry
        result = subprocess.run(command(name, get_current_context()), cwd='/opt/retail', timeout=timeout_s)
        if result.returncode == 2:
            raise AirflowFailException(f'{name}: sai hợp đồng/quality gate; xem console.log và failure.json')
        if result.returncode:
            raise RuntimeError(f'{name}: lỗi tạm thời, exit={result.returncode}')

    prepare = stage.override(task_id='prepare_snapshot')('prepare')
    # Dự báo là task riêng (S2, 2026-10-18), đúng dòng DAG trên sơ đồ kiến trúc. Lần chậm nhất đã đo 956 giây (local
    # b2b-01); 45 phút chừa chỗ cho máy bận. Lỗi hợp đồng dự báo exit 2 → AirflowFailException, không retry.
    forecast = stage.override(task_id='forecast_train_score', execution_timeout=timedelta(minutes=45))('forecast', 2640)
    build = stage.override(task_id='ingest_and_dbt_build')('build')
    validate = stage.override(task_id='quality_and_reader_gate')('validate')
    publish = stage.override(task_id='publish_release')('publish')
    prepare >> forecast >> build >> validate >> publish
