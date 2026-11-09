"""Nạp đợt demo local; cần chọn orders_enriched và shipments_realistic trong extensions.

Chỉ trigger tay, dừng ở validate. Admin công bố riêng trên app.
"""
from datetime import timedelta
import hashlib
import re
import subprocess

import pendulum
from airflow.sdk import DAG, Param, get_current_context, task
from airflow.exceptions import AirflowFailException


def command(stage, context):
    if stage not in ('prepare', 'forecast', 'build', 'validate'):
        raise ValueError('DAG nạp đợt không có stage công bố')
    params = context['params']
    dots, source = params['dots'], params['du_bao_tu']
    if not isinstance(dots, list) or not dots:
        raise ValueError('Cần ít nhất một thư mục đợt')
    pattern = (r'/opt/retail/(?:data_demo/[a-zA-Z0-9_-]{1,100}|'
               r'warehouse/pipeline/docker/nhap/[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}_dot/file)')
    if any(not isinstance(path, str) or not re.fullmatch(pattern, path) for path in dots):
        raise ValueError('Đường dẫn đợt không hợp lệ')
    target = params.get('target', 'duckdb')
    if target not in ('duckdb', 'databricks'):
        raise ValueError('Target không hợp lệ')
    run_id = params.get('pipeline_run_id')
    if run_id is not None and (not isinstance(run_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', run_id)):
        raise ValueError('Mã lượt pipeline không hợp lệ')
    request_id = params.get('request_id')
    if request_id is not None and (not isinstance(request_id, str) or not re.fullmatch(
            r'[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}_dot', request_id)):
        raise ValueError('Mã yêu cầu không hợp lệ')
    if not re.fullmatch(r'[a-f0-9]{24}', source):
        raise ValueError('Bản nguồn dự báo phải gồm 24 ký tự hex')
    run_id = run_id or hashlib.sha256(context['run_id'].encode()).hexdigest()[:24]
    args = ['/opt/pipeline/bin/python', '-m', 'scripts.pipeline.cli', stage,
            '--run-id', run_id, '--target', target, '--root', 'warehouse/pipeline/docker']
    if params.get('force'):
        args.append('--force')
    if stage == 'prepare':
        for path in dots:
            args += ['--dot', path]
        for extension in sorted(set(params.get('extensions', []))):
            if not re.fullmatch(r'[a-z][a-z0-9_]*', extension):
                raise ValueError('Tên phần mở rộng không hợp lệ')
            args += ['--extension', extension]
    if stage == 'forecast':
        args += ['--du-bao-tu', source]
    return args


with DAG(
    dag_id='retail_dot_pipeline',
    description='Nạp đợt, dừng sau kiểm tra; Admin công bố dashboard riêng.',
    start_date=pendulum.datetime(2026, 10, 11, tz='Asia/Ho_Chi_Minh'),
    schedule=None, catchup=False, is_paused_upon_creation=True, max_active_runs=1,
    dagrun_timeout=timedelta(hours=2),
    default_args={'retries': 2, 'retry_delay': timedelta(minutes=2), 'execution_timeout': timedelta(minutes=65),
                  'pool': 'retail_writer'},
    params={'target': Param('duckdb', enum=['duckdb', 'databricks']),
            'dots': Param([], type='array', items={'type': 'string'}),
            'pipeline_run_id': Param(None, type=['null', 'string'], pattern='^[a-zA-Z0-9_-]{1,100}$'),
            'request_id': Param(None, type=['null', 'string'], pattern='^[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}_dot$'),
            'du_bao_tu': Param(type='string', pattern='^[a-f0-9]{24}$'),
            'force': Param(False, type='boolean'),
            'extensions': Param([], type='array', items={'type': 'string', 'pattern': '^[a-z][a-z0-9_]*$'})},
    tags=['retail', 'demo'],
) as dag:
    @task
    def stage(name):
        result = subprocess.run(command(name, get_current_context()), cwd='/opt/retail', timeout=3800)
        if result.returncode == 2:
            raise AirflowFailException('Đợt không đạt hợp đồng/quality gate; xem nhật ký pipeline.')
        if result.returncode:
            raise RuntimeError(f'Stage {name} chưa thành công, exit={result.returncode}')

    prepare = stage.override(task_id='prepare_snapshot')('prepare')
    forecast = stage.override(task_id='forecast_from_source')('forecast')
    build = stage.override(task_id='ingest_and_dbt_build')('build')
    validate = stage.override(task_id='quality_and_reader_gate')('validate')
    prepare >> forecast >> build >> validate
