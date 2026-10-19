"""Chạy từ root: python -m scripts.pipeline.cli run --target duckdb --run-id demo-01.

Airflow gọi từng stage; registry/cloud và thư mục candidate chỉ do một writer quản lý.
Các bản ready không được build lại, kể cả retry sau lỗi publish.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from scripts.pipeline import snapshot
from scripts.pipeline.runtime import Databricks
from scripts.pipeline.state import Registry, atomic_json, writer_lock
from scripts.parity.compare_dwh import compare, SKIP

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps' / 'retail_app'))
# Thứ tự stage = thứ tự task của DAG: prepare_snapshot → forecast_train_score → ingest_and_dbt_build
# → quality_and_reader_gate → publish_release (S2, 2026-10-18: dự báo tách khỏi build thành stage riêng)
STAGES = ('prepare', 'forecast', 'build', 'validate', 'publish')
from dwh.releases import checked, allowed_versions, CONTROL_RELATION


def code_version():
    h = hashlib.sha256()
    for folder in ('retail_dbt/models', 'retail_dbt/macros', 'retail_dbt/tests', 'retail_dbt/seeds',
                   'scripts/pipeline', 'scripts/ingest', 'scripts/parity', 'scripts/forecast', 'apps/retail_app'):
        for p in sorted((ROOT / folder).rglob('*')):
            if p.suffix in ('.py', '.sql', '.yml', '.csv') and '__pycache__' not in p.parts:
                h.update(p.relative_to(ROOT).as_posix().encode())
                h.update(p.read_bytes().replace(b'\r\n', b'\n'))
    for name in ('retail_dbt/dbt_project.yml', 'retail_dbt/profiles.yml'):
        h.update((ROOT / name).read_bytes().replace(b'\r\n', b'\n'))
    return h.hexdigest()


def dbt_build(context, target, cloud=None):
    folder = Path(context['directory']) / target
    folder.mkdir(parents=True, exist_ok=True)
    vars_ = {k: context[k] for k in ('release_id', 'snapshot_id', 'code_version', 'snapshot_path')}
    if context.get('forecast_path'):   # bật rpt_forecast_* và test của chúng (retail_dbt/models/reporting/_forecast.yml)
        vars_['forecast_path'] = context['forecast_path']
    dbt = os.getenv('RETAIL_DBT_EXECUTABLE') or str(Path(sys.executable).with_name('dbt.exe' if os.name == 'nt' else 'dbt'))
    env = {**os.environ, 'PYTHONUTF8': '1', 'RETAIL_DUCKDB_BUILD_PATH': context['duckdb_path']}
    if cloud:
        env.update(cloud.dbt_env())
    with (folder / 'console.log').open('w', encoding='utf-8') as output:
        result = subprocess.run([dbt, 'build', '--project-dir', str(ROOT / 'retail_dbt'),
                                 '--profiles-dir', str(ROOT / 'retail_dbt'), '--target', target,
                                 '--target-path', str(folder), '--log-path', str(folder / 'logs'),
                                 '--no-partial-parse', '--vars', json.dumps(vars_)],
                                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=1800)
    if result.returncode:
        log = (folder / 'console.log').read_text(encoding='utf-8', errors='replace').lower()
        error_type = ConnectionError if any(x in log for x in (
            'connection refused', 'connection reset', 'timed out', 'timeout', 'temporarily unavailable',
            'too many requests', 'warehouse is stopped')) else ValueError
        raise error_type(f'dbt {target} thất bại; xem {folder / "console.log"}')
    verify_artifacts(folder, context, target)


def verify_artifacts(folder, context, target):
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    results = json.loads((folder / 'run_results.json').read_text(encoding='utf-8'))
    expected = {k: n for k, n in manifest['nodes'].items() if n['resource_type'] in ('model', 'seed', 'test')}
    actual = {r['unique_id']: r for r in results['results'] if r['unique_id'] in expected}
    if (not expected or set(expected) != set(actual)
            or manifest['metadata']['invocation_id'] != results['metadata']['invocation_id']
            or results.get('args', {}).get('which') != 'build'
            or results['args'].get('target') != target):
        raise ValueError('Artifact thiếu node, sai invocation/target hoặc không phải full build')
    for name, node in expected.items():
        if actual[name]['status'] != ('pass' if node['resource_type'] == 'test' else 'success'):
            raise ValueError(f'Quality gate: {name} không đạt')
        if node['resource_type'] != 'test' and not node['schema'].startswith(f"r_{context['release_id']}_"):
            raise ValueError('Artifact trỏ ra ngoài namespace candidate')
    if any(r['status'] not in ('pass', 'success') for r in results['results']):
        raise ValueError('Hook hoặc node không đạt')
    return manifest


def forecast_stage(context):
    """Stage `forecast` (task Airflow forecast_train_score, S2 2026-10-18): train, backtest và chọn ứng viên dự báo từ
    snapshot (scripts/forecast/stage.py); dbt ở stage build đọc kết quả thành rpt_forecast_*. Retry cùng run dùng lại kết
    quả đã có. ValueError (không hội tụ, hỏng kiểm tháng 8/2023) dừng pipeline, không retry."""
    from scripts.forecast import stage
    out = Path(context['directory']) / 'forecast'
    meta = stage.run(context['snapshot_path'], out, run_id=context['run_id'], snapshot_id=context['snapshot_id'])
    return out.as_posix(), {k: meta[k] for k in ('model_version', 'primary', 'selection_step', 'fits', 'seconds')}


def check_forecast(context):
    """Trước dbt: kết quả của stage forecast còn nguyên (cùng snapshot, cùng code dự báo, đúng hash file). Không train lại
    ở build; hỏng thì báo chạy lại stage forecast."""
    from scripts.forecast import stage
    out = Path(context.get('forecast_path') or '')
    meta_path = out / 'forecast_meta.json'
    if not context.get('forecast_path') or not meta_path.exists():
        raise ValueError('Chưa có kết quả stage forecast; chạy stage forecast trước build')
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    for f in stage.FILES:
        if not (out / f).exists():
            raise ValueError(f'Kết quả stage forecast thiếu {f}; chạy lại stage forecast')
        with (out / f).open('rb') as handle:
            if hashlib.file_digest(handle, 'sha256').hexdigest() != meta['sha256'][f]:
                raise ValueError(f'Kết quả stage forecast đổi sau khi ghi ({f}); chạy lại stage forecast')
    if meta.get('snapshot_id') != context['snapshot_id'] or meta.get('model_version') != stage.model_version():
        raise ValueError('Kết quả stage forecast không khớp snapshot / code dự báo của run; chạy lại stage forecast')


def validate_data(context, cloud=None):
    import duckdb
    rid = context['release_id']
    baseline = duckdb.connect(context['duckdb_path'], read_only=True)
    try:
        def local_query(sql):
            cur = baseline.execute(sql)
            return [d[0] for d in cur.description], cur.fetchall()
        fetch = cloud.query if cloud else local_query
        # Đối chứng độc lập ở từng ngày, dùng sales trong snapshot đã khóa.
        path = context['snapshot_path'].replace("'", "''")
        _, expected = local_query(f"select Date, Revenue, COGS from read_parquet('{path}/sales.parquet')")
        _, actual = fetch(f'select date_sk, revenue, cogs from r_{rid}_marts.fact_daily_sales where is_actual')
        from decimal import Decimal
        expected = {int(d.replace('-', '')): (Decimal(g), Decimal(c)) for d, g, c in expected}
        if len(actual) != len(expected) or {int(d): (Decimal(g), Decimal(c)) for d, g, c in actual} != expected:
            raise ValueError('G/COGS theo ngày không khớp snapshot sales')
        _, health = fetch(f'select status_code from r_{rid}_reporting.rpt_health_summary')
        if health != [('tot',)]:
            raise ValueError('Sức khỏe candidate không đạt')
        manifest = verify_artifacts(Path(context['directory']) / context['target'], context, context['target'])
        names = sorted({(n['schema'], n['name']) for n in manifest['nodes'].values()
                        if n['resource_type'] in ('model', 'seed')
                        and n['schema'] in (f'r_{rid}_marts', f'r_{rid}_reporting') and not SKIP(n['name'])})
        if cloud:
            for schema, name in names:
                statement = f'select * from {schema}.{name}'
                errors = compare(name, local_query(statement), fetch(statement))
                if errors:
                    raise ValueError(f'Parity {name}: ' + '; '.join(errors[:3]))
        return {'daily_rows': len(actual), 'relations_checked': len(names), 'cloud_parity': bool(cloud)}
    finally:
        baseline.close()


def _vars():
    import yaml
    return yaml.safe_load((ROOT / 'retail_dbt/dbt_project.yml').read_text(encoding='utf-8'))['vars']


def consumers():
    """(bảng của app, bảng của AI), mỗi bên gồm cả bảng tùy chọn: AI có ai_optional_relations (rpt_forecast_*, B3
    2026-10-15), app có app_optional_relations (ba bảng trang Dự báo, RV11). Lúc cấp quyền / kiểm reader chỉ lấy bảng
    tùy chọn có thật trong bản đang kiểm (present)."""
    cfg = _vars()
    return (cfg['app_read_relations'] + cfg.get('app_optional_relations', []),
            cfg['ai_readonly_relations'] + cfg.get('ai_optional_relations', []))


def optional_relations():
    cfg = _vars()
    return frozenset(cfg.get('ai_optional_relations', [])) | frozenset(cfg.get('app_optional_relations', []))


def present(logical, schema, exists):
    """Bảng bắt buộc giữ nguyên; bảng tùy chọn chỉ giữ khi có trong schema của bản (RV04, review Codex 2026-10-15):
    bản mới có dự báo thì được cấp quyền và thử đọc, bản trước B2b (rollback) không bị đòi bảng không tồn tại."""
    optional = optional_relations()
    return [r for r in logical if r not in optional or exists(schema, r.split('.')[1])]


def reader_grants(catalog, client, schema, logical):
    """Câu GRANT cho một reader. Registry đi trước bảng của bản mới: guard chế độ cũ của chat chỉ chấp nhận quyền
    trên r_<id>_reporting khi đã đọc được registry; cấp ngược thứ tự thì chat public bị khóa trong lúc cấp."""
    qualified = [CONTROL_RELATION] + [f"{schema}.{r.split('.')[1]}" for r in logical]
    out = [f'grant use catalog on catalog {catalog} to `{client}`']
    for s in dict.fromkeys(r.split('.')[0] for r in qualified):
        out.append(f'grant use schema on schema {catalog}.{s} to `{client}`')
        out += [f'grant select on table {catalog}.{r} to `{client}`' for r in qualified if r.split('.')[0] == s]
    return qualified, out


def verify_consumers(context, registry, cloud=None):
    """Cloud: thử đọc bằng CHÍNH các principal tiêu thụ, kiểm quyền cả phần thừa."""
    app, ai = consumers()
    if cloud is None:
        import duckdb
        path = registry.path.parent / context['artifact_path'] if context.get('artifact_path') else Path(context['duckdb_path'])
        with duckdb.connect(str(path), read_only=True) as con:
            def exists(schema, name):
                return con.execute('select count(*) from information_schema.tables where table_schema = ? '
                                   'and table_name = ?', [schema, name]).fetchone()[0] > 0
            for rel in set(present(app + ai, context['schema'], exists)):
                con.execute(f"select * from {context['schema']}.{rel.split('.')[1]} limit 1").fetchall()
        return
    from databricks import sql
    from databricks.sdk.core import Config
    from dwh.guarded import _check_dbx_identity
    def exists(schema, name):
        _, rows = cloud.query(f'select count(*) from {cloud.catalog}.information_schema.tables '
                              'where table_schema = ? and table_name = ?', (schema, name))
        return rows[0][0] > 0
    for kind, full in [('APP', app), ('AI', ai)]:
        logical = present(full, context['schema'], exists)
        client = os.getenv(f'RETAIL_{kind}_DBX_CLIENT_ID')
        secret = os.getenv(f'RETAIL_{kind}_DBX_CLIENT_SECRET')
        if not client or not secret or not re.fullmatch(r'[a-fA-F0-9-]{36}', client):
            raise ValueError(f'Thiếu danh tính đọc RETAIL_{kind}_DBX_CLIENT_ID/SECRET')
        if client == os.environ['RETAIL_PIPELINE_CLIENT_ID']:
            raise ValueError('Writer và reader phải là hai danh tính khác nhau')
        qualified, statements = reader_grants(cloud.catalog, client, context['schema'], logical)
        for statement in statements:
            cloud.query(statement)
        auth = Config(host=cloud.auth.host, client_id=client, client_secret=secret, auth_type='oauth-m2m')
        with sql.connect(server_hostname=cloud.auth.host.removeprefix('https://').rstrip('/'),
                         http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
                         credentials_provider=lambda: auth.authenticate, catalog=cloud.catalog,
                         session_configuration={'STATEMENT_TIMEOUT': '120'}) as con, con.cursor() as cur:
            allowed = allowed_versions(registry.read()['payload'], full)    # quyền dự báo của bản khác không thừa
            _check_dbx_identity(cur, client, allowed, cloud.catalog, frozenset(qualified))
            for rel in qualified:
                cur.execute(f'select * from {rel} limit 1')
                cur.fetchall()


HISTORY_FIELDS = ('run_id', 'stage', 'target', 'snapshot_id', 'code_version', 'release_id', 'started_at', 'finished_at',
                  'result', 'error_type')
HISTORY_TABLE = 'retail_control.run_history'   # cloud: writer sở hữu, KHÔNG grant cho SP reader (D1 = không, S3)


def _utc():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def record_history(root, entry):
    """Lịch sử lần chạy (S3, A4): mỗi stage và mỗi lần rollback, dù đạt, bỏ qua hay lỗi, thêm một dòng. Local: <root>/history.jsonl
    (chỉ thêm, không sửa). Target databricks: thêm cả bảng retail_control.run_history. Không ghi SQL, token hay nội dung exception
    (như failure.json). Không nằm trong r_<id>_ops (bản lỗi không bao giờ được công bố) và không sửa bản ghi release trong registry.
    Ghi lịch sử lỗi thì chỉ cảnh báo: không che lỗi gốc, không biến một lần publish đã đổi con trỏ thành lỗi."""
    try:
        path = Path(root) / 'history.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps({k: entry.get(k) for k in HISTORY_FIELDS}, ensure_ascii=False) + '\n')
        if entry.get('target') == 'databricks':
            cloud = Databricks()
            try:
                cloud.query(f'create table if not exists {HISTORY_TABLE} ('
                            + ', '.join(f'{k} string' for k in HISTORY_FIELDS) + ') using delta')
                cloud.query(f'insert into {HISTORY_TABLE} values (' + ', '.join('?' for _ in HISTORY_FIELDS) + ')',
                            [entry.get(k) for k in HISTORY_FIELDS])
            finally:
                cloud.close()
    except Exception as error:  # noqa: BLE001 — lỗi ghi lịch sử không được thay lỗi / kết quả của stage
        print(f'Cảnh báo: không ghi được lịch sử lần chạy ({type(error).__name__}); kết quả stage giữ nguyên.',
              file=sys.stderr)


def _entry(stage, run_id, target, started, result, source=None, error=None):
    source = source or {}
    return {'run_id': run_id, 'stage': stage, 'target': target, 'snapshot_id': source.get('snapshot_id'),
            'code_version': source.get('code_version'), 'release_id': source.get('release_id'), 'started_at': started,
            'finished_at': _utc(), 'result': result, 'error_type': type(error).__name__ if error is not None else None}


def execute(stage, *, run_id, target='duckdb', root='warehouse/pipeline', data='data', snapshot_id=None, force=False):
    """Chạy một stage và để lại một dòng lịch sử: dat (stage tiến lên), bo_qua (run bỏ qua hoặc stage đã xong từ trước), loi."""
    started = _utc()
    context_path = Path(root).resolve() / 'runs' / str(run_id) / 'context.json'
    before = _read_json(context_path)
    try:
        context = _execute(stage, run_id=run_id, target=target, root=root, data=data, snapshot_id=snapshot_id, force=force)
    except Exception as error:
        record_history(Path(root).resolve(), _entry(stage, run_id, target, started, 'loi', _read_json(context_path) or before,
                                                    error))
        raise
    done_before = before is not None and before.get('stage') == context.get('stage')
    result = 'bo_qua' if context.get('stage') == 'skipped' or done_before else 'dat'
    record_history(Path(root).resolve(), _entry(stage, run_id, target, started, result, context))
    return context


def _execute(stage, *, run_id, target='duckdb', root='warehouse/pipeline', data='data', snapshot_id=None, force=False):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', run_id):
        raise ValueError('run_id chỉ gồm chữ, số, gạch nối/gạch dưới; tối đa 100 ký tự')
    root = Path(root).resolve()
    directory = root / 'runs' / run_id
    context_path = directory / 'context.json'
    cloud = None
    with writer_lock(root):
        try:
            if stage == 'prepare':
                if context_path.exists():
                    context = json.loads(context_path.read_text(encoding='utf-8'))
                    if context['target'] != target:
                        raise ValueError('run_id đã dùng cho target khác')
                    return context
                if target == 'databricks':
                    cloud = Databricks()
                registry = Registry(root, cloud.query if cloud else None)
                registry.initialize()
                landing = root / 'snapshots'
                if snapshot_id:
                    if not re.fullmatch('[a-f0-9]{12}', snapshot_id):
                        raise ValueError('snapshot_id sai định dạng')
                    path = landing / snapshot_id
                    manifest = snapshot.validate(path)
                else:
                    path = snapshot.prepare(data, landing)
                    manifest = snapshot.validate(path)
                state = registry.read()['payload']
                revision = code_version()
                active = state['releases'].get(state['active'], {})
                skip = not force and active.get('snapshot_id') == manifest['snapshot_id'] and active.get('code_version') == revision
                rid = uuid.uuid4().hex[:24]
                context = {'run_id': run_id, 'target': target, 'release_id': rid, 'snapshot_id': manifest['snapshot_id'],
                           'snapshot_path': path.as_posix(), 'code_version': revision,
                           'directory': directory.as_posix(), 'duckdb_path': (directory / 'dbt.duckdb').as_posix(),
                           'schema': f'r_{rid}_reporting', 'expected_active': state['active'],
                           'started_at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                           'stage': 'skipped' if skip else 'prepared'}
                atomic_json(context_path, context)
                return context
            context = json.loads(context_path.read_text(encoding='utf-8'))
            if context['target'] != target:
                raise ValueError('Target không khớp lần prepare')
            if context['stage'] in ('published', 'skipped'):
                return context
            if context['code_version'] != code_version():
                raise ValueError('Code đổi giữa các stage; tạo run_id mới')
            manifest = snapshot.validate(context['snapshot_path'])
            if stage == 'forecast':
                # task riêng forecast_train_score (S2): không cần cloud hay registry; chỉ đọc snapshot, ghi runs/<id>/forecast
                if context['stage'] in ('forecasted', 'built', 'validated'):
                    return context
                if context['stage'] != 'prepared':
                    raise ValueError(f"Stage forecast cần run ở trạng thái prepared, đang là {context['stage']}")
                context['forecast_path'], context['forecast'] = forecast_stage(context)
                context['stage'] = 'forecasted'
                atomic_json(context_path, context)
                return context
            if target == 'databricks':
                cloud = Databricks()
            registry = Registry(root, cloud.query if cloud else None)
            if stage == 'build':
                if context['stage'] in ('built', 'validated'):
                    return context
                if context['release_id'] in registry.read()['payload']['releases']:
                    raise ValueError('Không được dựng lại phiên bản ready')
                if context['stage'] != 'forecasted':
                    raise ValueError('Chưa chạy stage forecast cho run này: chạy forecast trước build '
                                     '(DAG có task forecast_train_score giữa prepare_snapshot và ingest_and_dbt_build)')
                check_forecast(context)
                if cloud:
                    cloud.ingest(context, manifest)
                    cloud.ingest_forecast(context)
                dbt_build(context, 'duckdb')
                if cloud:
                    dbt_build(context, 'databricks', cloud)
                context['stage'] = 'built'
            elif stage == 'validate':
                if context['stage'] == 'validated':
                    return context
                if context['stage'] != 'built':
                    raise ValueError('Phải build trước validate')
                context['quality'] = validate_data(context, cloud)
                record = {k: context[k] for k in ('release_id', 'snapshot_id', 'code_version', 'run_id', 'schema', 'duckdb_path')}
                record['artifact_path'] = f"runs/{run_id}/dbt.duckdb"
                record['status'] = 'ready'
                registry.register(checked(record))
                verify_consumers(context, registry, cloud)
                context['stage'] = 'validated'
            elif stage == 'publish':
                if context['stage'] != 'validated':
                    raise ValueError('Phải validate trước publish')
                verify_consumers(context, registry, cloud)
                registry.publish(context['release_id'], context['expected_active'])
                context['stage'] = 'published'
            else:
                raise ValueError('Stage không hỗ trợ')
            atomic_json(context_path, context)
            return context
        except Exception as error:
            # Không ghi exception chứa SQL/token vào metadata chung.
            atomic_json(directory / 'failure.json', {'stage': stage, 'type': type(error).__name__,
                        'at': dt.datetime.now(dt.timezone.utc).isoformat()})
            raise
        finally:
            if cloud:
                cloud.close()


def read_history(root, target='duckdb', limit=20):
    """N lần chạy gần nhất, mới nhất trước. Local đọc <root>/history.jsonl; databricks đọc retail_control.run_history."""
    if target == 'databricks':
        cloud = Databricks()
        try:
            cols, rows = cloud.query(f'select {", ".join(HISTORY_FIELDS)} from {HISTORY_TABLE} '
                                     f'order by started_at desc, finished_at desc limit {int(limit)}')
        finally:
            cloud.close()
        return [dict(zip(HISTORY_FIELDS, r)) for r in rows]
    path = Path(root) / 'history.jsonl'
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue        # dòng ghi dở (máy tắt giữa chừng): bỏ qua, không làm hỏng cả lệnh
    return rows[::-1][:max(0, int(limit))]


def print_history(root, target='duckdb', limit=20):
    rows = read_history(root, target, limit)
    if not rows:
        print('Chưa có lần chạy nào được ghi.')
        return
    head = ('bắt đầu (UTC)', 'kết thúc', 'stage', 'kết quả', 'loại lỗi', 'run_id', 'release_id', 'snapshot', 'code')
    table = [(r.get('started_at') or '', (r.get('finished_at') or '')[11:], r.get('stage') or '', r.get('result') or '',
              r.get('error_type') or '', r.get('run_id') or '', (r.get('release_id') or '')[:12],
              r.get('snapshot_id') or '', (r.get('code_version') or '')[:12]) for r in rows]
    widths = [max(len(str(x[i])) for x in [head, *table]) for i in range(len(head))]
    for row in [head, *table]:
        print('  '.join(str(v).ljust(w) for v, w in zip(row, widths)).rstrip())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stage', choices=(*STAGES, 'run', 'rollback', 'history'))
    ap.add_argument('--run-id', help='bắt buộc, trừ lệnh history')
    ap.add_argument('--target', choices=('duckdb', 'databricks'), default='duckdb')
    ap.add_argument('--root', default='warehouse/pipeline')
    ap.add_argument('--data', default='data')
    ap.add_argument('--snapshot-id')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--release-id')
    ap.add_argument('--limit', type=int, default=20, help='history: số lần chạy gần nhất cần in')
    a = ap.parse_args()
    if a.stage == 'history':
        print_history(a.root, a.target, a.limit)
        return
    if not a.run_id:
        ap.error('cần --run-id')
    if a.stage == 'rollback':
        started, rollback_record, result = _utc(), {'release_id': a.release_id}, 'loi'
        try:
            if not a.release_id or not re.fullmatch('[a-f0-9]{24}', a.release_id):
                ap.error('rollback cần --release-id gồm 24 ký tự hex')
            with writer_lock(a.root):
                cloud = Databricks() if a.target == 'databricks' else None
                try:
                    registry = Registry(a.root, cloud.query if cloud else None)
                    state = registry.read()['payload']
                    if a.release_id not in state['releases']:
                        ready = sorted(r for r, rec in state['releases'].items() if rec.get('status') == 'ready')
                        ap.error(f'không có phiên bản {a.release_id} trong registry; các bản rollback được: '
                                 + (', '.join(ready) or 'chưa có'))
                    rollback_record = checked(state['releases'][a.release_id])
                    verify_consumers(rollback_record, registry, cloud)
                    registry.publish(a.release_id, state['active'])
                    atomic_json(Path(a.root) / 'rollbacks' / f'{uuid.uuid4().hex}.json',
                                {'run_id': a.run_id, 'from': state['active'], 'to': a.release_id})
                    result = 'bo_qua' if state['active'] == a.release_id else 'dat'
                finally:
                    if cloud:
                        cloud.close()
        except BaseException as error:     # cả SystemExit của ap.error: mã bản gõ sai cũng để lại một dòng lịch sử
            record_history(Path(a.root).resolve(), _entry('rollback', a.run_id, a.target, started, 'loi', rollback_record,
                                                          error))
            raise
        record_history(Path(a.root).resolve(), _entry('rollback', a.run_id, a.target, started, result, rollback_record))
        print('Đã khôi phục phiên bản ' + a.release_id)
        return
    for stage in STAGES if a.stage == 'run' else (a.stage,):
        result = execute(stage, run_id=a.run_id, target=a.target, root=a.root, data=a.data,
                         snapshot_id=a.snapshot_id, force=a.force)
        print(json.dumps({k: result[k] for k in ('run_id', 'release_id', 'snapshot_id', 'stage')}, ensure_ascii=False))


if __name__ == '__main__':
    # PowerShell/worker có thể dùng code page không hỗ trợ tiếng Việt.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    try:
        main()
    except (ValueError, FileNotFoundError) as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        sys.exit(2)
