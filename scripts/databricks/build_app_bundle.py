"""Dựng gói deploy Databricks Apps ở build/databricks_app/ (Git ignore) từ code đang checkout.

Giữ cấu trúc repo để `ROOT` của app (parents[3] của dwh/connection.py) trỏ đúng gốc gói:
  app.yaml                                ← deploy/databricks_app/
  requirements.txt                        ← apps/retail_app/ (dùng chung với Streamlit Community Cloud)
  apps/retail_app/**                      ← trừ tests/, __pycache__/, .pytest_cache/
  retail_dbt/...                          ← đúng các file ai_explain.metric_catalog.DEFINITION_FILES (chat ghi hash)
Không chép file .env.* (secret đi qua resource của app), không chép data/ hay warehouse/.

Chạy từ root repo:  .venv/Scripts/python.exe scripts/databricks/build_app_bundle.py
Rồi: databricks workspace import-dir build/databricks_app <đường dẫn workspace> --overwrite && databricks apps deploy ...
(`databricks sync` bỏ qua build/ vì bị gitignore; docs/ai_explain_nhat_ky.md)
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")       # Windows cp1252 không in được tiếng Việt
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build' / 'databricks_app'
sys.path.insert(0, str(ROOT / 'apps' / 'retail_app'))
from ai_explain.metric_catalog import DEFINITION_FILES  # noqa: E402

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
shutil.copy(ROOT / 'deploy' / 'databricks_app' / 'app.yaml', OUT / 'app.yaml')
shutil.copy(ROOT / 'apps' / 'retail_app' / 'requirements.txt', OUT / 'requirements.txt')
shutil.copytree(ROOT / 'apps' / 'retail_app', OUT / 'apps' / 'retail_app',
                ignore=shutil.ignore_patterns('tests', 'conftest.py', '__pycache__', '.pytest_cache', '*.pyc', '.env*'))
for f in DEFINITION_FILES:
    (OUT / f).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / f, OUT / f)

leaked = [p for p in OUT.rglob('*') if p.name.startswith('.env') or 'data' in p.relative_to(OUT).parts[:1]]
if leaked:
    sys.exit(f'Gói có file không được deploy: {leaked}')
rev = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, cwd=ROOT).stdout.strip()
dirty = subprocess.run(['git', 'status', '--porcelain', '--', 'apps/retail_app', 'deploy', 'retail_dbt'],
                       capture_output=True, text=True, cwd=ROOT).stdout.strip()
(OUT / 'apps' / 'retail_app' / 'BUILD_REVISION').write_text(f'{rev}{"+dirty" if dirty else ""}\n', encoding='utf-8')
n = sum(1 for p in OUT.rglob('*') if p.is_file())
print(f'Đã dựng {OUT.relative_to(ROOT)}: {n} file, code {rev}{" (CÓ thay đổi chưa commit)" if dirty else ""}')
