"""T2a: Volume, catalog và registry giả; không gọi cloud hay Docker."""
import csv
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest
import yaml

from scripts.ops import nhap_do as poll, don_kho_dot as cleanup
from scripts.ingest import auto_mapping, approval, tu_dong, extension_contract
from scripts.pipeline.state import Registry, atomic_json
from ui.kho_dot import KhoDia
from ui.kho_hop_dong import KhoHopDong, load_raw, chu_ky_nghiep_vu
from test_nhap_do import FakeCatalog, request as dot_request

ROOT = Path(__file__).resolve().parents[3]
MOT = '20261111T000000Z_abcdef_mot'
OTHER = '20261111T000001Z_abcdef_mot'
A, B = 'a'*24, 'b'*24
REAL_PROPOSE, REAL_REPORT = auto_mapping.propose, auto_mapping.render_report


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo = tmp_path/'repo'
    contracts = repo/'scripts/ingest/extensions'
    contracts.mkdir(parents=True)
    for name in ('orders_enriched', 'shipments_realistic'):
        shutil.copyfile(ROOT/'scripts/ingest/extensions'/f'{name}.yml', contracts/f'{name}.yml')
    model = repo/'retail_dbt/models/m.sql'
    model.parent.mkdir(parents=True)
    model.write_text("{{ extension_enabled('orders_enriched') }}", encoding='utf-8')
    monkeypatch.setattr(poll, 'REPO', repo)
    root = tmp_path/'pipeline'
    registry = Registry(root)
    registry.initialize()
    registry.register({'release_id':A, 'status':'ready', 'snapshot_id':'a'*12, 'run_id':'base'})
    registry.publish(A, None)
    atomic_json(root/'snapshots'/('a'*12)/'manifest.json',
                {'sources':{'shipments_realistic':{'mo_rong':True}}})
    kho = KhoDia(tmp_path/'volume')
    _, approved = KhoHopDong(kho, contracts).current('orders_enriched')
    proposal = {'nguon':{'de_xuat':'orders'}, 'cot':[
        {'ten_trong_file': c, 'loai':'khop', 'khong_ep_duoc':0,
         'thong_ke':{'mau':['PRIVATE_CELL']}} for c in approved['header']],
        'xung_dot_khoa':{'da_kiem':True, 'id_trung_khac_noi_dung':0, 'anh_xa':[{'id_trong_file':'PRIVATE_ID'}]}}
    monkeypatch.setattr(auto_mapping, 'propose', lambda *args: deepcopy(proposal))
    monkeypatch.setattr(auto_mapping, 'render_report', lambda body: 'Báo cáo không chứa mẫu ô.')
    def cloud_factory():
        class Cloud:
            def query(self, sql, params=()):
                assert sql.startswith('select version, payload')
                state = registry.read()
                return [], [(state['version'], json.dumps(state['payload']))]
            def close(self):
                pass
        return Cloud()
    return SimpleNamespace(repo=repo, contracts=contracts, root=root, registry=registry,
        kho=kho, catalog=FakeCatalog(), proposal=proposal, approved=approved, cloud_factory=cloud_factory)


def request(env, rid=MOT, content=None):
    if content is None:
        content = (','.join(env.approved['header'])+'\n'+','.join('1' for _ in env.approved['header'])+'\n').encode()
    folder = poll.request_path(rid)
    item = {'ten':'orders_enriched.csv', 'so_byte':len(content), 'sha256':hashlib.sha256(content).hexdigest()}
    env.kho.ghi_moi(folder+'/yeu_cau.json', json.dumps({'id':rid, 'loai':'mot_file',
        'nguoi_gui':'owner', 'vai_tro':'quan_ly', 'mo_ta':'', 'ngay_gui':'2026-11-11', 'file':item}).encode())
    env.kho.ghi_moi(folder+'/file/'+item['ten'], content)
    env.kho.ghi_json_so_tiep(folder+'/su_kien', {'toi':'da_gui'})
    return rid


def row(env, rid=MOT):
    return poll._requests(env.kho)[rid]


def advance(env, rid, target, **extra):
    poll._event(env.kho, row(env,rid), target, **extra)


def approved(env, rid=MOT, *, duong='tu_dong', patch=None, bad_hash=False, include_signature=True, bad_signature=False):
    request(env, rid)
    advance(env, rid, 'dang_doc')
    doc = tu_dong.hop_dong_cua_luot(env.approved, env.approved['header'],
        f'ui_nhap_cloud/{rid}/orders_enriched.csv', 1, '2026-11-11')
    doc.update(patch or {})
    raw = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False).encode()
    env.kho.ghi_moi(poll.request_path(rid)+'/hop_dong/orders_enriched.yml', raw)
    sha = hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()
    extra = {}
    if include_signature:
        extra['chu_ky_nghiep_vu'] = '0'*64 if bad_signature else chu_ky_nghiep_vu(doc)
    advance(env, rid, 'da_duyet', duong=duong, ten_mo_rong='orders_enriched',
            hop_dong_sha256='0'*64 if bad_hash else sha, **extra)
    return doc, raw


def scan(env):
    return poll.quet(env.kho, env.catalog, root=env.root, cloud_factory=env.cloud_factory, call=lambda args: pytest.fail('Không chạy CLI khi quét yêu cầu'))


def test_auto_path_artifacts_and_no_cell_values(env):
    request(env)
    scan(env)
    current = row(env)
    assert current['trang_thai'] == 'cho_chay' and current['duong'] == 'tu_dong'
    assert [e['toi'] for e in current['lich_su']] == ['da_gui','dang_doc','da_duyet','cho_chay']
    doc, _ = poll._mot_contract(env.kho, current)
    assert doc['file'] == f'ui_nhap_cloud/{MOT}/orders_enriched.csv'
    assert doc['duyet_boi'].startswith('he_thong (')
    assert current['chu_ky_nghiep_vu'] == chu_ky_nghiep_vu(doc)
    for filename in ('mapping_de_xuat.yml','bao_cao_mapping.md'):
        raw = env.kho.doc(poll.request_path(MOT)+'/de_xuat/'+filename)
        assert b'PRIVATE_CELL' not in raw and b'PRIVATE_ID' not in raw


def test_real_mapping_small_orders_file(env, monkeypatch):
    data = ROOT/'data'
    # Hai đơn có cùng zip để zip không bị xem là khóa đơn của geography
    # trong mẫu quá nhỏ; không nới ngưỡng suy nguồn của auto_mapping.
    cores, by_zip = [], {}
    with (data/'orders.csv').open(encoding='utf-8-sig', newline='') as handle:
        for index, item in enumerate(csv.DictReader(handle)):
            if item['zip'] in by_zip:
                cores = [by_zip[item['zip']], item]
                break
            by_zip[item['zip']] = item
            if index >= 5000:
                break
    assert len(cores) == 2
    extras = {'sales_employee_id':'E1','sales_employee_name':'PRIVATE_PERSON',
              'marital_status':'single','education_level':'uni','years_experience':'1','comment':'PRIVATE_COMMENT'}
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=env.approved['header'])
    writer.writeheader()
    for core in cores:
        writer.writerow({c: core.get(c, extras.get(c,'')) for c in env.approved['header']})
    request(env, content=out.getvalue().encode())
    monkeypatch.setattr(auto_mapping, 'propose', lambda path, _: REAL_PROPOSE(path, data))
    monkeypatch.setattr(auto_mapping, 'render_report', REAL_REPORT)
    scan(env)
    assert row(env)['trang_thai'] == 'cho_chay', row(env).get('ly_do')
    for filename in ('mapping_de_xuat.yml','bao_cao_mapping.md'):
        raw = env.kho.doc(poll.request_path(MOT)+'/de_xuat/'+filename)
        assert b'PRIVATE_PERSON' not in raw and b'PRIVATE_COMMENT' not in raw


@pytest.mark.parametrize('damage,reason', [('missing','thieu_cot'),('unknown','chua_ro_nguon')])
def test_needs_human_no_trigger(env, damage, reason):
    if damage == 'missing':
        env.proposal['cot'] = env.proposal['cot'][:-1]
    else:
        env.proposal['nguon']['de_xuat'] = 'chua_ro'
    request(env)
    scan(env)
    assert row(env)['trang_thai'] == 'cho_duyet'
    assert reason in [r['ma'] for r in row(env)['ly_do']]
    assert poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=env.cloud_factory) == {'trigger':[]}


@pytest.mark.parametrize('damage', ['sha', 'file', 'name', 'model', 'latest', 'download', 'signature'])
def test_untrusted_contract_and_file_never_trigger(env, monkeypatch, damage):
    patch = {'file':'sales.csv'} if damage == 'file' else ({'ten':'other'} if damage == 'name' else None)
    approved(env, patch=patch, bad_hash=damage == 'sha', bad_signature=damage == 'signature')
    if damage == 'model':
        monkeypatch.setattr(approval, 'has_dbt_model', lambda *a: False)
    if damage == 'latest':
        env.kho.ghi_moi('hop_dong_da_duyet/orders_enriched/v2.yml', b'{broken')
    if damage == 'download':
        path = env.kho.root/poll.request_path(MOT)/'file/orders_enriched.csv'
        path.write_bytes(b'changed')
    scan(env)
    assert row(env)['trang_thai'] == 'loi'
    assert not poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=env.cloud_factory)['trigger']


def ready_previous(env, *, state='da_kiem', dashboard=False, include_signature=True):
    doc, raw = approved(env, OTHER, include_signature=include_signature)
    advance(env, OTHER, 'cho_chay')
    advance(env, OTHER, 'dang_chay')
    advance(env, OTHER, 'da_kiem', release_id=B)
    if state in ('tren_dashboard','da_tra'):
        advance(env, OTHER, 'tren_dashboard')
    if state=='da_tra':
        advance(env, OTHER, 'da_tra')
    env.registry.register({'release_id':B,'status':'ready','chi_dashboard':True,
                           'snapshot_id':'b'*12,'run_id':'old'})
    manifest=env.root/'snapshots'/('b'*12)/'manifest.json'
    atomic_json(manifest,{'sources':{'orders_enriched':{
        'csv_sha256':row(env,OTHER)['file']['sha256']}}})
    if dashboard:
        env.registry.publish_dashboard(B,None)
    return manifest


@pytest.mark.parametrize('state',['da_kiem','tren_dashboard','da_tra'])
@pytest.mark.parametrize('dashboard',[False,True])
def test_duplicate_uses_event_signature_without_old_directory(env,monkeypatch,state,dashboard):
    ready_previous(env,state=state,dashboard=dashboard)
    assert not (env.root/'nhap'/OTHER).exists()
    assert not (env.root/'runs/old').exists()
    monkeypatch.setattr(poll,'_read_stage',lambda *a:pytest.fail('Không đọc context/hợp đồng cũ'))
    original=env.kho.doc
    def read(path):
        if path.startswith(poll.request_path(OTHER)+'/hop_dong/'):
            pytest.fail('Không đọc lại hợp đồng cũ trên Volume')
        return original(path)
    monkeypatch.setattr(env.kho,'doc',read)
    request(env)
    scan(env)
    assert row(env)['trang_thai']=='khong_moi'
    assert row(env)['chu_ky_nghiep_vu']==row(env,OTHER)['chu_ky_nghiep_vu']
    assert not poll.ket_thuc(env.kho,{},root=env.root,cloud_factory=env.cloud_factory)['trigger']


@pytest.mark.parametrize('dashboard',[False,True])
def test_duplicate_different_contract_version_runs(env,dashboard):
    ready_previous(env,dashboard=dashboard)
    approved(env,patch={'phien_ban':2})
    scan(env)
    assert row(env)['trang_thai']=='cho_chay'
    assert row(env)['chu_ky_nghiep_vu']!=row(env,OTHER)['chu_ky_nghiep_vu']


@pytest.mark.parametrize('dashboard',[False,True])
def test_duplicate_missing_old_signature_runs(env,dashboard):
    ready_previous(env,dashboard=dashboard,include_signature=False)
    request(env)
    scan(env)
    assert row(env)['trang_thai']=='cho_chay'


@pytest.mark.parametrize('dashboard',[False,True])
@pytest.mark.parametrize('damage',['missing','json','sources'])
def test_duplicate_bad_old_manifest_only_blocks_dashboard(env,dashboard,damage):
    manifest=ready_previous(env,dashboard=dashboard)
    if damage=='missing':
        manifest.unlink()
    elif damage=='json':
        manifest.write_bytes(b'{broken')
    else:
        manifest.write_bytes(b'{"sources":[]}')
    request(env)
    scan(env)
    assert row(env)['trang_thai']==('loi' if dashboard else 'cho_chay')
    if not dashboard:
        assert poll.ket_thuc(env.kho,{},root=env.root,cloud_factory=env.cloud_factory)['trigger']


def test_batch_dashboard_does_not_make_mot_duplicate(env):
    approved(env)
    env.registry.register({'release_id':B,'status':'ready','co_du_lieu_tong_hop':True,
                           'snapshot_id':'b'*12,'run_id':'batch'})
    atomic_json(env.root/'snapshots'/('b'*12)/'manifest.json',{'sources':{'orders_enriched':{
        'csv_sha256':row(env)['file']['sha256']}}})
    env.registry.publish_dashboard(B,None)
    scan(env)
    assert row(env)['trang_thai']=='cho_chay'


@pytest.mark.parametrize('pointer',['c'*24,'bad','',[]])
def test_duplicate_broken_dashboard_still_errors(env,pointer):
    approved(env)
    current=env.registry.read()
    env.registry.save(current,dict(current['payload'],dashboard=pointer))
    scan(env)
    assert row(env)['trang_thai']=='loi'
    assert not poll.ket_thuc(env.kho,{},root=env.root,cloud_factory=env.cloud_factory)['trigger']
    assert env.registry.read()['payload']['active']==A


def test_duplicate_requires_same_extension_name(env):
    ready_previous(env)
    path=env.kho.root/poll.request_path(OTHER)/'su_kien/000003.json'
    event=json.loads(path.read_bytes())
    event['ten_mo_rong']='shipments_realistic'
    path.write_text(json.dumps(event),encoding='utf-8')
    request(env)
    scan(env)
    assert row(env)['trang_thai']=='cho_chay'


def test_trigger_conf_uses_active_repo_extensions_and_no_dots(env):
    approved(env)
    scan(env)
    result = poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=env.cloud_factory)
    conf = result['trigger'][0]['conf']
    assert conf['dots'] == [] and conf['chi_dashboard'] is True and conf['du_bao_tu'] == A
    assert conf['extensions'] == ['orders_enriched','shipments_realistic']
    folder = Path(conf['extension_dir'])
    assert (folder/'shipments_realistic.yml').read_bytes() == (env.contracts/'shipments_realistic.yml').read_bytes()
    assert load_raw('orders_enriched',(folder/'orders_enriched.yml').read_bytes())['file'].startswith('ui_nhap_cloud/')
    assert row(env)['trang_thai'] == 'dang_chay'


@pytest.mark.parametrize('case', ['free','busy','pending','manual','registry_error','older_pending','bad_context','bad_pointer',
    'all_done','older_invalid','older_broken','older_list','older_missing_kind'])
def test_completion_and_auto_dashboard_policy(env, monkeypatch, case):
    approved(env, duong='tay' if case == 'manual' else 'tu_dong')
    scan(env)
    result = poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=env.cloud_factory)
    run = result['trigger'][0]['airflow_run_id']
    env.registry.register({'release_id':B,'status':'ready','chi_dashboard':True,'snapshot_id':'b'*12,'run_id':run})
    if case == 'busy':
        env.registry.publish_dashboard(B,None)
    if case == 'bad_pointer':
        current=env.registry.read()
        env.registry.save(current,dict(current['payload'],dashboard=''))
    older_cases=('older_pending','all_done','older_invalid','older_broken','older_list','older_missing_kind')
    if case=='pending' or case in older_cases:
        env.kho.ghi_json_so_tiep('lenh', {'loai':'tra'})
    if case in older_cases:
        env.kho.ghi_json_so_tiep('lenh', {'loai':'tra'})
        env.kho.ghi_moi('lenh/000002.ket_qua.json',b'{"ket_qua":"dat"}')
    old_results={'all_done':b'{"ket_qua":"loi"}','older_invalid':b'{"ket_qua":"cho"}',
                 'older_broken':b'{broken','older_list':b'[]','older_missing_kind':b'{}'}
    if case in old_results:
        env.kho.ghi_moi('lenh/000001.ket_qua.json',old_results[case])
    context = {'stage':'validated','release_id':B}
    context['co_du_lieu_tong_hop' if case == 'bad_context' else 'chi_dashboard'] = True
    atomic_json(env.root/'runs'/run/'context.json', context)
    if case == 'registry_error':
        monkeypatch.setattr(poll,'_payload',lambda *a: (_ for _ in ()).throw(ValueError('PRIVATE_DETAIL')))
    poll.ket_thuc(env.kho, {run:'success'}, root=env.root, cloud_factory=env.cloud_factory)
    assert row(env)['trang_thai'] == ('loi' if case == 'bad_context' else 'da_kiem')
    names = poll.sequence_names(env.kho.liet_ke('lenh'))
    auto = [json.loads(env.kho.doc('lenh/'+n)) for n in names]
    auto = [item for item in auto if item.get('ai') == 'airflow']
    assert bool(auto) == (case in ('free','all_done'))
    if auto:
        assert {k:auto[0][k] for k in ('loai','request_id','release_id','ai')} == {'loai':'dat','request_id':MOT,'release_id':B,'ai':'airflow'}
    if case in ('busy','pending','registry_error','bad_pointer','older_pending',
                'older_invalid','older_broken','older_list','older_missing_kind'):
        assert env.kho.doc(poll.request_path(MOT)+'/thong_bao.json')
    assert env.registry.read()['payload']['active'] == A


def test_mot_command_has_new_flag_and_never_touches_ledger(env):
    approved(env)
    advance(env,MOT,'cho_chay')
    advance(env,MOT,'dang_chay')
    advance(env,MOT,'da_kiem',release_id=B)
    dot_id = '20261111T000002Z_abcdef_dot'
    dot_request(env,dot_id,status='tren_dashboard')
    env.kho.ghi_json_so_tiep('lenh',{'loai':'dat','request_id':MOT,'release_id':B})
    calls=[]
    poll._process_command(env.kho,poll._requests(env.kho),lambda args: calls.append(args) or 0, [])
    assert '--xac-nhan-nguon-moi' in calls[0] and '--xac-nhan-tong-hop' not in calls[0]
    assert row(env)['trang_thai'] == 'tren_dashboard' and row(env,dot_id)['trang_thai'] == 'da_tra'
    assert env.kho.liet_ke('so_dot') == []
    env.kho.ghi_json_so_tiep('lenh',{'loai':'tra'})
    poll._process_command(env.kho,poll._requests(env.kho),lambda args: 0, [])
    assert row(env)['trang_thai'] == row(env,dot_id)['trang_thai'] == 'da_tra'


@pytest.mark.parametrize('contracts,execute', [(False,False),(True,False),(True,True)])
def test_cleanup_contracts_opt_in(env, monkeypatch, contracts, execute):
    from databricks.sdk.errors import NotFound
    base = cleanup.GOC_DUOC_PHEP
    seen, deleted = [], []
    class Files:
        def list_directory_contents(self,path):
            seen.append(path)
            if path == base+'/hop_dong_da_duyet':
                return [SimpleNamespace(path=path+'/v1.yml',is_directory=False)]
            raise NotFound('không có')
        def delete(self,path): deleted.append(path)
        def delete_directory(self,path): deleted.append(path)
    client=SimpleNamespace(files=Files())
    monkeypatch.setattr(poll,'_default_store',lambda: (SimpleNamespace(root=base),client))
    monkeypatch.setattr(sys,'argv',['don']+(['--ca-hop-dong'] if contracts else [])+(['--thuc-hien'] if execute else []))
    cleanup.main()
    assert (base+'/hop_dong_da_duyet' in seen) == contracts
    assert bool(deleted) == execute


def test_cleanup_rejects_root_outside_allowed(monkeypatch):
    monkeypatch.setattr(poll,'_default_store',lambda: (SimpleNamespace(root='/Volumes/other'),None))
    monkeypatch.setattr(sys,'argv',['don','--ca-hop-dong','--thuc-hien'])
    with pytest.raises(SystemExit):
        cleanup.main()


@pytest.mark.parametrize('used,target', [(317,'cho_chay'), (318,'het_cho')])
def test_mot_quota_and_repeated_scan(env,used,target):
    env.catalog.count = used
    approved(env)
    scan(env)
    assert row(env)['trang_thai'] == target
    before = env.kho.doc(poll.request_path(MOT) + '/su_kien/000004.json')
    scan(env)
    assert row(env)['trang_thai'] == target
    assert env.kho.doc(poll.request_path(MOT) + '/su_kien/000004.json') == before


def test_contract_changed_after_queue_is_rechecked_before_trigger(env):
    approved(env)
    scan(env)
    path=env.kho.root/poll.request_path(MOT)/'hop_dong/orders_enriched.yml'
    path.write_bytes(path.read_bytes()+b'\n# changed\n')
    assert not poll.ket_thuc(env.kho,{},root=env.root,cloud_factory=env.cloud_factory)['trigger']
    assert row(env)['trang_thai'] == 'loi'


def test_auto_dashboard_unmarked_registry_record_only_notifies(env):
    env.registry.register({'release_id':B,'status':'ready','snapshot_id':'b'*12,'run_id':'run'})
    poll._auto_dashboard(env.kho, {'id':MOT,'release_id':B}, env.root, env.cloud_factory)
    assert env.kho.liet_ke('lenh') == []
    assert json.loads(env.kho.doc(poll.request_path(MOT)+'/thong_bao.json'))['thong_bao']
    assert env.registry.read()['payload']['active'] == A
