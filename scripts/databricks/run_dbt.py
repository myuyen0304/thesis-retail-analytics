"""Chạy dbt trên target `databricks` (lab) mà không phải dán token: lấy host + access token OAuth từ profile của
Databricks CLI (`databricks auth login --profile <profile>`), http_path từ id SQL warehouse, rồi gọi dbt của .venv-databricks.

Kết quả dbt (manifest, run_results) ghi vào retail_dbt/target_databricks/, không đè bằng chứng local ở retail_dbt/target/.

Chạy từ root repo:
  .venv-databricks/Scripts/python.exe scripts/databricks/run_dbt.py build
  (mọi tham số khác được chuyển nguyên cho dbt, vd. `build -s staging`)
Profile, warehouse, catalog lấy từ .env.databricks.local (DATABRICKS_CONFIG_PROFILE, DATABRICKS_WAREHOUSE_ID,
RETAIL_DATABRICKS_CATALOG — mặc định retail_lab); --profile / --warehouse-id ghi đè.
Application id của service principal AI (RETAIL_AI_DBX_CLIENT_ID trong .env.ai.local) được chuyển cho hook cấp quyền.
"""
import argparse
import os
import subprocess
import sys

from databricks.sdk.core import Config


def local_config(path='.env.databricks.local'):
    """Giá trị đã điền trong .env.databricks.local (file cá nhân, Git ignore). Biến môi trường cùng tên được ưu tiên."""
    cfg = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            k, sep, v = line.strip().partition('=')
            if sep and not k.startswith('#'):
                cfg[k.strip()] = v.strip().strip("'\"")
    return {k: os.environ.get(k) or v for k, v in cfg.items() if os.environ.get(k) or v}

c = local_config()
ap = argparse.ArgumentParser()
ap.add_argument('--profile', default=c.get('DATABRICKS_CONFIG_PROFILE'))
ap.add_argument('--warehouse-id', default=c.get('DATABRICKS_WAREHOUSE_ID'))
a, dbt_args = ap.parse_known_args()
if not (a.profile and a.warehouse_id):
    sys.exit('Thiếu profile / warehouse id: điền DATABRICKS_CONFIG_PROFILE, DATABRICKS_WAREHOUSE_ID '
             'trong .env.databricks.local hoặc truyền --profile / --warehouse-id.')

cfg = Config(profile=a.profile)
token = cfg.authenticate().get('Authorization', '').removeprefix('Bearer ')
if not token:
    sys.exit(f'Không lấy được token từ profile {a.profile} — chạy lại `databricks auth login --profile {a.profile}`.')
env = {**os.environ, 'PYTHONUTF8': '1',
       'DATABRICKS_HOST': cfg.host.removeprefix('https://').rstrip('/'),
       'DATABRICKS_HTTP_PATH': f'/sql/1.0/warehouses/{a.warehouse_id}',
       'DATABRICKS_TOKEN': token,
       'DATABRICKS_CATALOG': c.get('RETAIL_DATABRICKS_CATALOG', 'retail_lab')}
# Hook on-run-end (macros/ai_readonly_grants.sql) cấp lại SELECT 14 bảng cho service principal chỉ-đọc của chat AI.
# Lấy application id (không lấy secret) từ .env.ai.local; chưa có thì hook bỏ qua.
principal = os.environ.get('RETAIL_AI_DBX_PRINCIPAL') or local_config('.env.ai.local').get('RETAIL_AI_DBX_CLIENT_ID')
if principal:
    env['RETAIL_AI_DBX_PRINCIPAL'] = principal
dbt = os.path.join('.venv-databricks', 'Scripts', 'dbt.exe')
sys.exit(subprocess.call([dbt, *dbt_args, '--project-dir', 'retail_dbt', '--profiles-dir', 'retail_dbt',
                          '--target', 'databricks', '--target-path', 'target_databricks'], env=env))
