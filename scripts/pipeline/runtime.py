"""Adapter Databricks dùng danh tính ghi riêng; không đọc profile OAuth cá nhân."""
import os
import re


def identifier(value):
    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', value):
        raise ValueError('Tên catalog/schema không hợp lệ')
    return value


class Databricks:
    def __init__(self):
        from databricks import sql
        from databricks.sdk.core import Config
        required = ('DATABRICKS_HOST', 'DATABRICKS_WAREHOUSE_ID', 'RETAIL_PIPELINE_CLIENT_ID', 'RETAIL_PIPELINE_CLIENT_SECRET')
        if any(not os.getenv(k) for k in required):
            raise ValueError('Thiếu cấu hình writer: ' + ', '.join(required))
        self.catalog = identifier(os.getenv('RETAIL_DATABRICKS_CATALOG', 'retail_lab'))
        self.auth = Config(host=os.environ['DATABRICKS_HOST'], client_id=os.environ['RETAIL_PIPELINE_CLIENT_ID'],
                           client_secret=os.environ['RETAIL_PIPELINE_CLIENT_SECRET'], auth_type='oauth-m2m')
        self.connection = sql.connect(server_hostname=self.auth.host.removeprefix('https://').rstrip('/'),
                                      http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
                                      credentials_provider=lambda: self.auth.authenticate, catalog=self.catalog,
                                      session_configuration={'STATEMENT_TIMEOUT': '600'})

    def query(self, statement, params=()):
        with self.connection.cursor() as cur:
            cur.execute(statement, list(params))
            return [d[0].lower() for d in (cur.description or [])], cur.fetchall() if cur.description else []

    def dbt_env(self):
        return {'DATABRICKS_HOST': self.auth.host.removeprefix('https://').rstrip('/'),
                'DATABRICKS_HTTP_PATH': f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
                'DATABRICKS_CATALOG': self.catalog,
                'DATABRICKS_TOKEN': self.auth.authenticate()['Authorization'].removeprefix('Bearer ')}

    def ingest(self, context, manifest):
        from pathlib import Path
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient(config=self.auth)
        raw = f"r_{context['release_id']}_raw"
        self.query(f'create schema if not exists {raw}')
        self.query('create schema if not exists pipeline_landing')
        self.query('create volume if not exists pipeline_landing.snapshots')
        volume = f"/Volumes/{self.catalog}/pipeline_landing/snapshots/{context['snapshot_id']}"
        for name, entry in manifest['sources'].items():
            with (Path(context['snapshot_path']) / f'{name}.parquet').open('rb') as f:
                w.files.upload(f'{volume}/{name}.parquet', f, overwrite=True)
            self.query(f"create or replace table {raw}.{name} as select *, current_timestamp() as _loaded_at "
                       f"from read_files('{volume}/{name}.parquet', format => 'parquet')")
            _, rows = self.query(f'select count(*), count(distinct _src_row), min(_src_row), max(_src_row) from {raw}.{name}')
            if tuple(rows[0]) != (entry['rows'], entry['rows'], 1, entry['rows']):
                raise ValueError(f'{name}: raw không giữ nguyên dòng nguồn')
        self.query(f'create or replace table {raw}._ingest_log '
                   '(loaded_at timestamp, source string, row_count bigint, file_md5 string, seconds double) using delta')
        for name, entry in manifest['sources'].items():
            self.query(f'insert into {raw}._ingest_log values (cast(? as timestamp), ?, ?, ?, 0)',
                       [context['started_at'], name, entry['rows'], entry['csv_md5']])

    def close(self):
        self.connection.close()
