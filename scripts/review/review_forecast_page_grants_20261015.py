"""Đối chiếu bảng trang Dự báo đọc với danh sách app reader pipeline cấp quyền."""
import json
from pathlib import Path
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'apps/retail_app'))
from dwh import forecast_queries
from scripts.pipeline import cli


def main():
    state = json.loads((ROOT / 'warehouse/pipeline/state.json').read_text(encoding='utf-8'))['payload']
    rec = state['releases'][state['active']]
    app, ai = cli.consumers()
    page_relations = set(forecast_queries.SOURCE.values())
    _, grants = cli.reader_grants('retail_lab', 'app_sp', rec['schema'], app)
    with duckdb.connect(rec['duckdb_path'], read_only=True) as con:
        present = {r for r in page_relations if con.execute(
            'select count(*) from information_schema.tables where table_schema = ? and table_name = ?',
            [rec['schema'], r.split('.')[1]]).fetchone()[0] > 0}
    payload = dict(release_id=rec['release_id'], present_page_relations=sorted(present),
                   app_reader_missing=sorted(present - set(app)),
                   ai_reader_relations=sorted(present & set(ai)),
                   app_grant_statements_for_page=[s for s in grants if any(r.split('.')[1] in s for r in present)])
    out = ROOT / 'warehouse/reviews/ai_gd2_20261015/page_grants.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return int(bool(payload['app_reader_missing']))


if __name__ == '__main__':
    raise SystemExit(main())
