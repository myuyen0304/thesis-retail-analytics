"""Cấp quyền đọc bản đang phục vụ cho SP của Databricks Apps (S9, PM chọn A ngày 2026-10-20).

Pipeline chỉ cấp quyền cho SP bản public (RETAIL_APP_DBX_*) và SP chat (RETAIL_AI_DBX_*); SP riêng của Databricks Apps
không nằm trong danh sách đó, nên sau mỗi lần publish bản MỚI phải chạy lại script này. Dùng danh tính writer của
pipeline (đọc .env.airflow.local, không ghi, không in secret) và đúng câu GRANT của pipeline (`reader_grants`):
retail_control.state + các bảng trang app của bản active. SP app không có secret để thử đăng nhập; kiểm lại bằng
`databricks grants get-effective ... --principal <client>`.

Chạy từ root repo (mặc định chỉ in câu lệnh, thêm --thuc-hien mới cấp):
  .venv/Scripts/python.exe -m scripts.databricks.cap_quyen_sp_app --client <service_principal_client_id> [--thuc-hien]
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')       # Windows cp1252 không in được tiếng Việt
ROOT = Path(__file__).resolve().parents[2]


def load_env(path):
    """Nạp KEY=VALUE vào môi trường của tiến trình này; không in giá trị."""
    for line in path.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--client', required=True, help='service_principal_client_id của app (databricks apps get)')
    ap.add_argument('--thuc-hien', action='store_true', help='chạy GRANT; bỏ trống thì chỉ in câu lệnh')
    a = ap.parse_args()
    if not re.fullmatch(r'[a-fA-F0-9-]{36}', a.client):
        raise SystemExit('client phải là UUID của service principal')
    load_env(ROOT / '.env.airflow.local')
    if a.client in (os.getenv('RETAIL_PIPELINE_CLIENT_ID'), os.getenv('RETAIL_AI_DBX_CLIENT_ID')):
        raise SystemExit('client trùng writer hoặc SP chat; script này chỉ dành cho SP của Databricks Apps')

    from scripts.pipeline.cli import consumers, present, reader_grants
    from scripts.pipeline.runtime import Databricks
    from scripts.pipeline.state import Registry
    from dwh.releases import checked

    cloud = Databricks()
    state = Registry(ROOT, sql=cloud.query).read()['payload']
    record = state['releases'][state['active']]
    checked(record)
    schema = record['schema']

    def exists(s, name):
        _, rows = cloud.query(f'select count(*) from {cloud.catalog}.information_schema.tables '
                              'where table_schema = ? and table_name = ?', (s, name))
        return rows[0][0] > 0

    logical = present(consumers()[0], schema, exists)
    _, statements = reader_grants(cloud.catalog, a.client, schema, logical)
    print(f'Bản active: {state["active"]} ({schema}); {len(logical)} bảng trang app + retail_control.state')
    for statement in statements:
        print(('CHẠY  ' if a.thuc_hien else 'IN    ') + statement)
        if a.thuc_hien:
            cloud.query(statement)
    print('Xong.' if a.thuc_hien else 'Chưa cấp gì. Thêm --thuc-hien để chạy.')


if __name__ == '__main__':
    main()
