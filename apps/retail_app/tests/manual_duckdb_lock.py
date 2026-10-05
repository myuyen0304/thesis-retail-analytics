"""Kiểm tay (không chạy trong pytest vì mất ~1 phút): app đọc DuckDB trong lúc `dbt build --target duckdb` ghi file.

Chạy từ root repo, ở hai terminal:
    1) PYTHONUTF8=1 .venv/Scripts/python.exe apps/retail_app/tests/manual_duckdb_lock.py 60
    2) (sau ~2 giây) PYTHONUTF8=1 .venv/Scripts/dbt.exe build --project-dir retail_dbt --profiles-dir retail_dbt --target duckdb
Kết quả lần chạy 2026-09-27: dbt 155/155 PASS; app đọc ok 80, lỗi 27 (IOException: file đang bị dùng).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dwh.connection import read_sql  # noqa: E402

seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60
ok = fail = 0
errors = set()
t0 = time.time()
while time.time() - t0 < seconds:
    try:
        read_sql('select count(*) from reporting.rpt_revenue_yearly', 'duckdb')
        ok += 1
    except Exception as e:
        fail += 1
        errors.add(f'{type(e).__name__}: {str(e)[:120]}')
    time.sleep(0.5)
print(f'app đọc DuckDB: ok {ok}, lỗi {fail}')
for e in sorted(errors):
    print(' ', e)
