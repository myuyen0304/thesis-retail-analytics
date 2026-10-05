"""Chạy dbt trên target `snowflake` bằng thông tin trong .env.snowflake.local (key-pair, không password).

Kết quả dbt (manifest, run_results) ghi vào retail_dbt/target_snowflake/, không đè bằng chứng local ở retail_dbt/target/.

Chạy từ root repo:
  .venv/Scripts/python.exe scripts/snowflake/run_dbt.py build
  (mọi tham số được chuyển nguyên cho dbt, vd. `build -s staging`, `debug`)
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ingest'))
from snapshot import local_config  # noqa: E402

c = local_config('.env.snowflake.local')
if not c.get('SNOWFLAKE_ACCOUNT'):
    sys.exit('Thiếu SNOWFLAKE_ACCOUNT trong .env.snowflake.local — chạy scripts/snowflake/bootstrap.py rồi điền.')
env = {**os.environ, **{k: v for k, v in c.items() if k.startswith('SNOWFLAKE_')}, 'PYTHONUTF8': '1'}
env['SNOWFLAKE_PRIVATE_KEY_PATH'] = os.path.expanduser(env.get('SNOWFLAKE_PRIVATE_KEY_PATH', ''))
dbt = os.path.join('.venv', 'Scripts', 'dbt.exe')
sys.exit(subprocess.call([dbt, *sys.argv[1:], '--project-dir', 'retail_dbt', '--profiles-dir', 'retail_dbt',
                          '--target', 'snowflake', '--target-path', 'target_snowflake'], env=env))
