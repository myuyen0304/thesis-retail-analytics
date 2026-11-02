"""Báo cáo và dọn có kiểm soát các schema của bản dữ liệu cũ.

Chạy qua stdin trong container: python - --root ... --catalog ...
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

from scripts.pipeline.runtime import Databricks, identifier
from scripts.pipeline.state import Registry, writer_lock


HEX = re.compile(r'[a-f0-9]{24}\Z')
SCHEMA = re.compile(r'r_([a-f0-9]{24})_(raw|staging|intermediate|marts|reporting|ops)\Z')
SUFFIXES = ('raw', 'staging', 'intermediate', 'marts', 'reporting', 'ops')
FINISHED = frozenset(('skipped', 'published', 'validated'))


class Blocked(Exception):
    """Quy tắc giữ bản chặn toàn bộ lệnh xóa."""


class InputError(ValueError):
    """Lỗi đầu vào do chính script kiểm; thông báo an toàn để in cho PM."""


def utc_now():
    return datetime.now(timezone.utc)


def schema_set(rid):
    return {f'r_{rid}_{suffix}' for suffix in SUFFIXES}


def rows_as_dicts(result):
    columns, rows = result
    return [dict(zip(columns, row)) for row in rows]


def inventory(cloud, catalog):
    """Lấy cả schema trống; INFORMATION_SCHEMA.TABLES chỉ dùng đếm đối tượng."""
    _, rows = cloud.query(f'SHOW SCHEMAS IN {catalog}')
    schemas = {str(row[0]).lower() for row in rows}
    tables = rows_as_dicts(cloud.query(
        f'SELECT table_schema, table_type FROM {catalog}.information_schema.tables'))
    views = rows_as_dicts(cloud.query(
        f'SELECT table_schema, table_name, view_definition FROM {catalog}.information_schema.views'))
    return schemas, tables, views


def contexts_at(root):
    contexts = []
    for path in sorted((Path(root) / 'runs').glob('*/context.json')):
        contexts.append(json.loads(path.read_text(encoding='utf-8')))
    return contexts


def unfinished(context):
    return context.get('stage') not in FINISHED


def recent_unfinished(contexts, now):
    for context in contexts:
        if not unfinished(context):
            continue
        started = context.get('started_at')
        try:
            when = datetime.fromisoformat(started.replace('Z', '+00:00'))
            if when.tzinfo is None:
                # cli.py ghi UTC không kèm múi giờ: %Y-%m-%d %H:%M:%S.
                when = when.replace(tzinfo=timezone.utc)
            else:
                when = when.astimezone(timezone.utc)
        except (AttributeError, TypeError, ValueError):
            # Không đoán lượt chưa kết thúc có còn chạy hay không.
            yield context
            continue
        if now - timedelta(hours=2) <= when <= now:
            yield context


def rollback_id(payload, schemas):
    target = payload.get('dich_rollback') or {}
    rid = target.get('release_id') if isinstance(target, dict) else None
    record = payload.get('releases', {}).get(rid)
    active = payload.get('active')
    if (not isinstance(rid, str) or not HEX.fullmatch(rid) or rid == active
            or not isinstance(record, dict) or record.get('status') != 'ready'
            or record.get('release_id') != rid or not schema_set(rid) <= schemas):
        return None
    return rid


def plan_deletion(payload, schemas, contexts, views, requested, overrides=(), *, now):
    """Hàm thuần: xét toàn bộ lệnh trước khi cho phép một câu DROP nào."""
    releases = payload.get('releases', {})
    active = payload.get('active')
    targets = tuple(dict.fromkeys(requested))
    reasons = []
    if not active or active not in releases:
        reasons.append('G1: active rỗng hoặc không có trong releases')
    if active in targets:
        reasons.append('G1: yêu cầu xóa active')
    rollback = rollback_id(payload, schemas)
    if rollback is None:
        reasons.append('G2: chưa có đích rollback hợp lệ và đủ sáu schema')
    elif rollback in targets:
        reasons.append('G2: yêu cầu xóa đích rollback')
    if active in releases and not schema_set(active) <= schemas:
        reasons.append('G3: active không còn đủ sáu schema')
    if rollback and not schema_set(rollback) <= schemas:
        reasons.append('G3: đích rollback không còn đủ sáu schema')
    if any(recent_unfinished(contexts, now)):
        reasons.append('G4: có lượt chưa kết thúc bắt đầu trong vòng hai giờ hoặc thiếu thời điểm bắt đầu')

    selected = set()
    known_deleted = payload.get('da_xoa', {})
    for rid in targets:
        if rid in known_deleted and rid not in releases and not schema_set(rid) & schemas:
            continue
        if rid not in releases and not schema_set(rid) & schemas:
            reasons.append(f'Không tìm thấy bản {rid} trong registry hoặc catalog')
            continue
        selected.add(rid)
        if rid not in overrides and any(unfinished(c) and c.get('release_id') == rid for c in contexts):
            reasons.append(f'G5: context chưa kết thúc tham chiếu bản {rid}')

    selected_schemas = set().union(*(schema_set(rid) for rid in selected)) if selected else set()
    for view in views:
        source_schema = str(view.get('table_schema', '')).lower()
        if source_schema == 'information_schema':
            continue  # View hệ thống không chứa truy vấn nghiệp vụ của một bản.
        if source_schema in selected_schemas or not selected_schemas:
            continue
        definition = view.get('view_definition')
        if definition is None:
            reasons.append('G6: không đọc được định nghĩa một view ngoài bộ')
            break
        if any(f'r_{rid}_' in str(definition).lower() for rid in selected):
            reasons.append('G6: view ngoài bộ tham chiếu bản cần xóa')
            break
    return tuple(sorted(selected)), tuple(dict.fromkeys(reasons))


def checked_payload(payload):
    releases = payload.get('releases')
    active = payload.get('active')
    if (not isinstance(releases, dict) or active not in releases
            or any(not isinstance(rec, dict) or rec.get('status') != 'ready'
                   for rec in releases.values())):
        raise Blocked('Registry sau dọn phải giữ active và mọi bản còn lại ở trạng thái ready')


def removed_payload(payload, selected, when):
    """Giữ nguyên các khóa khác; không sửa status của bất kỳ bản nào."""
    updated = dict(payload)
    releases = dict(payload['releases'])
    deleted = dict(payload.get('da_xoa', {}))
    for rid in selected:
        record = releases.pop(rid, {})
        if not record and rid in deleted:
            continue  # Lần save trước có thể đã thành công rồi mất ACK.
        deleted[rid] = {key: record.get(key) for key in
                        ('release_id', 'snapshot_id', 'code_version', 'run_id', 'schema')}
        deleted[rid]['release_id'] = rid
        deleted[rid]['xoa_luc'] = when.strftime('%Y-%m-%dT%H:%M:%SZ')
    updated['releases'] = releases
    updated['da_xoa'] = deleted
    checked_payload(updated)
    return updated


def quota_info(cloud):
    """Quota metastore toàn cục; lỗi quyền/API chỉ làm thiếu dòng quota."""
    try:
        if hasattr(cloud, 'quota_info'):
            return cloud.quota_info()
        from databricks.sdk import WorkspaceClient
        workspace = WorkspaceClient(config=cloud.auth)
        metastore = workspace.metastores.current().metastore_id
        quota = workspace.resource_quotas.get_quota('METASTORE', metastore, 'table-quota').quota_info
        if quota is None or quota.quota_count is None or quota.quota_limit is None:
            return None
        return int(quota.quota_count), int(quota.quota_limit)
    except Exception:
        return None


def print_report(payload, schemas, tables, views, contexts, quota):
    releases = payload.get('releases', {})
    by_rid = {}
    for name in schemas:
        match = SCHEMA.fullmatch(name)
        if match:
            by_rid.setdefault(match[1], set()).add(name)
    active = payload.get('active')
    rollback = rollback_id(payload, schemas)
    now = utc_now()
    pending = {c.get('release_id') for c in contexts if unfinished(c)}
    for rid in sorted(set(releases) | set(by_rid)):
        rec = releases.get(rid, {})
        owned = by_rid.get(rid, set())
        if rid == active:
            role = 'active'
        elif rid == rollback:
            role = 'dich_rollback'
        elif rid in pending:
            role = 'dang_do'
        elif rid in releases and owned != schema_set(rid):
            role = 'mat_schema'
        elif rid in releases:
            role = 'ready'
        else:
            role = 'mo_coi'
        relevant = [t for t in tables if t.get('table_schema') in owned]
        view_count = sum(str(t.get('table_type', '')).upper() == 'VIEW' for t in relevant)
        count = len(relevant) - view_count
        _, reasons = plan_deletion(payload, schemas, contexts, views, [rid], now=now)
        allowed = not reasons
        reason = '; '.join(reasons) if reasons else 'vẫn kiểm lại sau khi lấy khóa'
        print(f"{rid} | {role} | bảng={count} view={view_count} | "
              f"snapshot_id={rec.get('snapshot_id', '-')} code_version={str(rec.get('code_version') or '-')[:8]} "
              f"run_id={rec.get('run_id', '-')} | có thể xóa={'có' if allowed else 'không'} | {reason}")
    total = sum(str(t.get('table_type', '')).upper() != 'VIEW' for t in tables)
    print(f'Tổng bảng trong catalog: {total}')
    if quota is None:
        print('Không đọc được quota')
    else:
        used, limit = quota
        remaining = limit - used
        print(f'Quota metastore: {used}/{limit}; chỗ còn lại: {remaining}')
        if remaining < 100:
            print('CẢNH BÁO: còn dưới 100 chỗ bảng')
    print('Bảng đã xóa có thể còn được tính vào quota một thời gian.')
    if rollback and active in releases:
        current_code = releases[active].get('code_version')
        rollback_code = releases[rollback].get('code_version')
        if current_code != rollback_code:
            print('CẢNH BÁO: code_version đích rollback khác active; lịch 08:00 có thể dừng khi dựng/publish bản mới.')


def execute_locked(root, cloud, registry, requests, overrides):
    before = registry.read()
    payload = before['payload']
    schemas, _, views = inventory(cloud, cloud.catalog)
    if all(rid in payload.get('da_xoa', {}) and rid not in payload.get('releases', {})
           and not schema_set(rid) & schemas for rid in requests):
        print('Đã xóa trước đó; không có gì cần làm.')
        return
    contexts = contexts_at(root)
    selected, reasons = plan_deletion(payload, schemas, contexts, views, requests, overrides, now=utc_now())
    if reasons:
        raise Blocked('; '.join(reasons))
    checked_payload(payload)
    if not selected:
        print('Đã xóa trước đó; không có gì cần làm.')
        return
    # Không ghi registry khi một DROP hoặc bước kiểm sau DROP thất bại.
    for rid in selected:
        for schema in sorted(schema_set(rid) & schemas):
            if not SCHEMA.fullmatch(schema):
                raise Blocked('Tên schema không khớp mẫu bảo vệ')
            cloud.query(f'DROP SCHEMA IF EXISTS {cloud.catalog}.{schema} CASCADE')
        schemas = inventory(cloud, cloud.catalog)[0]
        if schema_set(rid) & schemas:
            raise RuntimeError('Schema vẫn tồn tại sau DROP')
    for attempt in range(2):
        latest = registry.read() if attempt else before
        if attempt:
            schemas, _, views = inventory(cloud, cloud.catalog)
            if any(schema_set(rid) & schemas for rid in selected):
                raise RuntimeError('Schema xuất hiện lại khi thử ghi registry')
            _, reasons = plan_deletion(latest['payload'], schemas, contexts_at(root), views,
                                       requests, overrides, now=utc_now())
            if reasons:
                raise Blocked('; '.join(reasons))
            if all(rid not in latest['payload'].get('releases', {})
                   and rid in latest['payload'].get('da_xoa', {}) for rid in selected):
                break  # Save đã thành công, chỉ mất xác nhận.
        updated = removed_payload(latest['payload'], selected, utc_now())
        try:
            registry.save(latest, updated)
            break
        except RuntimeError:
            if attempt:
                raise
    for rid in selected:
        print(f'Đã dọn {rid}. Registry không tự khôi phục.')
        print('Gợi ý khôi phục thủ công chưa kiểm chứng sau DROP SCHEMA CASCADE; hỏi DE trước khi làm.')
        print('Nếu DE xác nhận có thể phục hồi, phải làm cho từng schema của bản:')
        for suffix in SUFFIXES:
            schema = f'{cloud.catalog}.r_{rid}_{suffix}'
            print(f'  CREATE SCHEMA IF NOT EXISTS {schema}; UNDROP TABLE {schema}.<ten_bang>;')


@contextmanager
def deletion_lock(root):
    """Chỉ lỗi lấy khóa là G7; lỗi SQL bên trong vẫn là lỗi mã 1."""
    lock = writer_lock(root)
    try:
        lock.__enter__()
    except OSError as error:
        raise Blocked('G7: không lấy được writer_lock(root)') from error
    try:
        yield
    finally:
        lock.__exit__(None, None, None)


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument('--root', default='warehouse/pipeline/docker')
    command.add_argument('--catalog', required=True)
    command.add_argument('--xoa', action='append', default=[])
    command.add_argument('--thuc-hien', action='store_true')
    command.add_argument('--dat-dich-rollback')
    command.add_argument('--cho-xoa-ban-do', action='append', default=[])
    return command


def main(argv=None, *, cloud_factory=Databricks, registry_factory=Registry):
    try:
        args = parser().parse_args(argv)
        if args.dat_dich_rollback and (args.xoa or args.thuc_hien):
            raise InputError('Không đặt đích rollback cùng lệnh xóa')
        if args.thuc_hien and not args.xoa:
            raise InputError('--thuc-hien cần --xoa')
        if args.cho_xoa_ban_do and not args.xoa:
            raise InputError('--cho-xoa-ban-do cần --xoa')
        for rid in [*args.xoa, *args.cho_xoa_ban_do, *([args.dat_dich_rollback] if args.dat_dich_rollback else [])]:
            if not HEX.fullmatch(rid):
                raise InputError('Mã bản phải đúng 24 ký tự hex thường, không có tiền tố')
        if set(args.cho_xoa_ban_do) - set(args.xoa):
            raise InputError('Mã cho xóa bản dở phải nằm trong --xoa')
        try:
            identifier(args.catalog)
        except ValueError as error:
            raise InputError('Tên catalog không hợp lệ') from error
        cloud = cloud_factory()
        try:
            if args.catalog != cloud.catalog:
                raise InputError('--catalog không khớp catalog của kết nối writer')
            registry = registry_factory(args.root, cloud.query)
            if args.thuc_hien:
                with deletion_lock(args.root):
                    execute_locked(args.root, cloud, registry, args.xoa, args.cho_xoa_ban_do)
            elif args.dat_dich_rollback:
                with writer_lock(args.root):
                    before = registry.read()
                    schemas, _, _ = inventory(cloud, args.catalog)
                    rid = args.dat_dich_rollback
                    rec = before['payload'].get('releases', {}).get(rid)
                    if (rid == before['payload'].get('active') or not isinstance(rec, dict)
                            or rec.get('status') != 'ready' or rec.get('release_id') != rid
                            or not schema_set(rid) <= schemas):
                        raise Blocked('Đích rollback phải là bản ready, khác active và còn đủ sáu schema')
                    payload = dict(before['payload'])
                    payload['dich_rollback'] = {'release_id': rid, 'dat_luc': utc_now().strftime('%Y-%m-%dT%H:%M:%SZ')}
                    registry.save(before, payload)
                    print(f'Đã đặt đích rollback: {rid}')
            else:
                before = registry.read()
                schemas, tables, views = inventory(cloud, args.catalog)
                contexts = contexts_at(args.root)
                print_report(before['payload'], schemas, tables, views, contexts, quota_info(cloud))
                if args.xoa:
                    selected, reasons = plan_deletion(before['payload'], schemas, contexts, views,
                                                      args.xoa, args.cho_xoa_ban_do, now=utc_now())
                    print('Kế hoạch --xoa: ' + ', '.join(args.xoa))
                    print('Không ghi gì; thêm --thuc-hien để thực hiện.')
                    if reasons:
                        print('Bị chặn nếu thực hiện: ' + '; '.join(reasons))
                    else:
                        print('Các schema khớp mẫu sẽ xóa: ' + ', '.join(
                            sorted(set().union(*(schema_set(rid) & schemas for rid in selected)))))
            return 0
        finally:
            cloud.close()
    except Blocked as error:
        print(str(error), file=sys.stderr)
        return 2
    except InputError as error:
        print(str(error), file=sys.stderr)
        return 1
    except SystemExit as error:
        return 0 if error.code == 0 else 1
    except Exception as error:
        # Driver/SDK có thể kèm thông tin nhạy cảm trong thông báo lỗi.
        print(f'Lỗi: {type(error).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    sys.exit(main())
