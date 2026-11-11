"""Dò đợt qua Files API mỗi 5 phút; không công bố bản dữ liệu."""
from datetime import timedelta
import json
import subprocess

import pendulum
from airflow.sdk import DAG, get_current_context, task
from airflow.exceptions import AirflowException
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator


def _call(stage, states=None):
    command = ['/opt/pipeline/bin/python', '-m', 'scripts.ops.nhap_do', stage]
    if states is not None:
        command += ['--trang-thai', json.dumps(states)]
    result = subprocess.run(command, cwd='/opt/retail', timeout=600, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode:
        raise AirflowException(f'Dò đợt {stage} lỗi, exit={result.returncode}')
    return json.loads(result.stdout.strip().splitlines()[-1])


with DAG(
    dag_id='nhap_du_lieu_do',
    start_date=pendulum.datetime(2026, 11, 9, tz='Asia/Ho_Chi_Minh'),
    schedule='*/5 * * * *', catchup=False, max_active_runs=1,
    is_paused_upon_creation=True, dagrun_timeout=timedelta(minutes=20),
    default_args={'retries': 0}, tags=['retail', 'nhap_dot'],
) as dag:
    @task
    def quet():
        return _call('quet')

    @task
    def doc_trang_thai(scanned):
        ti = get_current_context()['ti']
        states = {}
        for row in scanned['dang_chay']:
            run_id = row['airflow_run_id']
            count = ti.get_dr_count(dag_id='retail_dot_pipeline', run_ids=[run_id])
            states[run_id] = (ti.get_dagrun_state('retail_dot_pipeline', run_id) if count else None)
        return states

    @task
    def ket_thuc(states):
        result = _call('ket_thuc', states)
        return [{'trigger_run_id': row['airflow_run_id'], 'conf': row['conf']}
                for row in result['trigger']]

    scanned = quet()
    states = doc_trang_thai(scanned)
    finished = ket_thuc(states)
    triggered = TriggerDagRunOperator.partial(task_id='trigger', trigger_dag_id='retail_dot_pipeline',
                                               skip_when_already_exists=True,
                                               wait_for_completion=False).expand_kwargs(finished)
    finished >> triggered
