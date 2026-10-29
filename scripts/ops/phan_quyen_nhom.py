"""In câu GRANT cho group người dùng trên một bản dữ liệu (docs/phan_quyen.md §3.2). Chỉ in, không chạy.

Chạy từ root sau mỗi lần publish, rồi PM dán vào SQL editor của Databricks (bằng tài khoản admin):

    .venv/Scripts/python.exe scripts/ops/phan_quyen_nhom.py --release <id bản active>
    .venv/Scripts/python.exe scripts/ops/phan_quyen_nhom.py --release <id mới> --bo-ban-cu <id bản trước>

Mã bản active xem ở trang Sức khỏe dữ liệu hoặc `warehouse/pipeline/.../context.json` (release_id, 24 ký tự).
Group được cấp theo schema; service principal của app và chat vẫn cấp theo từng bảng ở stage validate (scripts/pipeline/cli.py),
script này không đụng tới. Không bao giờ cấp cho `account users` hay `_workspace_users_*` (§4 mục 2): cấp như vậy thì SP của
chat có quyền thừa và guard khóa mọi câu chat (đã xảy ra ngày 2026-10-25).
"""
import argparse
import re

CATALOG = 'retail_lab'
PHAN_TICH = ('marts', 'reporting')                                 # DA/BI
KY_SU = ('raw', 'staging', 'intermediate', 'marts', 'reporting')   # data engineer; raw/staging có cột mức Cấm (§3.2)
CONTROL = ('state', 'run_history')                                 # retail_control, chỉ data engineer đọc
_RELEASE = re.compile(r'^[0-9a-f]{24}$')
_CAM = re.compile(r'^(account users|users|_workspace_users.*)$', re.IGNORECASE)


def _release(value: str) -> str:
    if not _RELEASE.match(value):
        raise argparse.ArgumentTypeError(f'mã bản phải là 24 ký tự hex, nhận được {value!r}')
    return value


def _group(value: str) -> str:
    if _CAM.match(value.strip()):
        raise argparse.ArgumentTypeError(f'không cấp cho group toàn workspace {value!r} (docs/phan_quyen.md §4 mục 2)')
    return value.strip()


def statements(release: str, phan_tich: str, ky_su: str, old: str | None = None) -> list[str]:
    out = [f'-- Bản {release}: group {phan_tich} (DA/BI), {ky_su} (data engineer)']
    for g in (phan_tich, ky_su):
        out.append(f'grant use catalog on catalog {CATALOG} to `{g}`;')
    for layer in PHAN_TICH:
        out.append(f'grant use schema, select on schema {CATALOG}.r_{release}_{layer} to `{phan_tich}`;')
    for layer in KY_SU:
        out.append(f'grant use schema, select on schema {CATALOG}.r_{release}_{layer} to `{ky_su}`;')
    out.append(f'grant use schema on schema {CATALOG}.retail_control to `{ky_su}`;')
    out += [f'grant select on table {CATALOG}.retail_control.{t} to `{ky_su}`;' for t in CONTROL]
    if old:
        out.append(f'-- Thu quyền trên bản cũ {old}: group chỉ đọc bản đang phục vụ')
        for g, layers in ((phan_tich, PHAN_TICH), (ky_su, KY_SU)):
            out += [f'revoke use schema, select on schema {CATALOG}.r_{old}_{layer} from `{g}`;' for layer in layers]
    out.append('-- Kiểm sau khi chạy: chat public vẫn trả lời (guard không báo quyền thừa); '
               f'`show grants on schema {CATALOG}.r_{release}_marts`.')
    return out


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description='In câu GRANT cho group người dùng trên một bản dữ liệu (không chạy).')
    p.add_argument('--release', required=True, type=_release, help='mã bản active, 24 ký tự hex')
    p.add_argument('--bo-ban-cu', type=_release, help='mã bản trước, để thu quyền group trên bản đó')
    p.add_argument('--nhom-phan-tich', default='retail-phan-tich', type=_group)
    p.add_argument('--nhom-ky-su', default='retail-ky-su', type=_group)
    a = p.parse_args(argv)
    if a.bo_ban_cu == a.release:
        p.error('--bo-ban-cu trùng --release')
    print('\n'.join(statements(a.release, a.nhom_phan_tich, a.nhom_ky_su, a.bo_ban_cu)))


if __name__ == '__main__':
    main()
