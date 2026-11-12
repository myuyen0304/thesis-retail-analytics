"""T2: kho, hợp đồng và trang web với Volume/Neon giả; không gọi cloud."""
from pathlib import Path
import subprocess
import sys

import pytest

from ui.kho_dot import KhoDia, DaCo
from ui.kho_hop_dong import KhoHopDong
from ui.trang_thai_dot import phat_lai, loai_cua, request_path
from ui.nhap_dot import LABELS_MOT

ROOT = Path(__file__).resolve().parents[3]
MOT = '20261111T000000Z_abcdef_mot'


@pytest.mark.parametrize('manual', [False, True])
def test_replay_mot_paths(manual):
    steps = ['da_gui', 'dang_doc'] + (['cho_duyet'] if manual else []) + [
        'da_duyet', 'het_cho', 'cho_chay', 'dang_chay', 'loi', 'cho_chay',
        'dang_chay', 'da_kiem', 'tren_dashboard', 'da_tra', 'tren_dashboard']
    events = [(n, {'toi': step, 'duong': 'tay' if manual else 'tu_dong',
                    'ten_mo_rong': 'orders_enriched', 'hop_dong_sha256': 'a'*64,
                    'ly_do': [], 'cot_moi': ['bonus']}) for n, step in enumerate(steps, 1)]
    result = phat_lai(events, 'mot_file')
    assert result['trang_thai'] == 'tren_dashboard'
    assert result['ten_mo_rong'] == 'orders_enriched' and result['cot_moi'] == ['bonus']
    assert phat_lai(events)['trang_thai'] == 'hong'
    assert loai_cua(MOT) == 'mot_file' and loai_cua(MOT[:-3] + 'dot') == 'dot'
    assert request_path(MOT) == 'yeu_cau/' + MOT
    assert LABELS_MOT['khong_moi'] == 'Không có gì mới'


@pytest.mark.parametrize('extra', [{'duong': 1}, {'duong': 'khac'}, {'ly_do': {}},
    {'ly_do': [{'ma':'x'}]}, {'ten_mo_rong': []}, {'hop_dong_sha256': None}, {'cot_moi': [3]}])
def test_replay_mot_rejects_bad_fields(extra):
    assert phat_lai([(1, {'toi':'da_gui', **extra})], 'mot_file')['trang_thai'] == 'hong'


def test_replay_dot_unchanged_and_bad_step():
    assert phat_lai([(1,{'toi':'da_gui'}),(2,{'toi':'dang_kiem'})])['trang_thai'] == 'dang_kiem'
    assert phat_lai([(1,{'toi':'da_gui'}),(2,{'toi':'da_kiem'})], 'mot_file')['trang_thai'] == 'hong'


def test_volume_contract_versions_rejection_and_bad_latest(tmp_path):
    kho = KhoDia(tmp_path)
    registry = KhoHopDong(kho)
    meta, doc = registry.current('orders_enriched')
    assert meta['phien_ban'] == 1
    assert kho.liet_ke('hop_dong_da_duyet') == []  # Repo v1 không bị chép lên Volume.
    next_meta, upgraded = registry.write('orders_enriched', doc, 'de', 'test', expected=1)
    assert next_meta['phien_ban'] == 2
    assert registry.current('orders_enriched')[1] == upgraded
    with pytest.raises(DaCo):
        registry.write('orders_enriched', doc, 'other', 'test', expected=1)
    registry.reject('orders_enriched', ['Bonus'], 'Không cần', 'de')
    assert registry.rejected('orders_enriched', ['bonus'])
    assert not registry.rejected('orders_enriched', ['other'])
    kho.ghi_moi('hop_dong_da_duyet/orders_enriched/v3.yml', b'{broken')
    with pytest.raises(ValueError):
        registry.current('orders_enriched')


def test_concurrent_contract_write_loser_gets_daco(tmp_path, monkeypatch):
    kho = KhoDia(tmp_path)
    registry = KhoHopDong(kho)
    _, doc = registry.current('orders_enriched')
    original = kho.ghi_moi
    def rival(path, raw):
        original(path, raw)
        original(path, raw)
    monkeypatch.setattr(kho, 'ghi_moi', rival)
    with pytest.raises(DaCo):
        registry.write('orders_enriched', doc, 'de', 'test', expected=1)


def test_contract_module_imports_without_streamlit_duckdb_or_state(tmp_path):
    code = ("import sys; sys.path.insert(0, sys.argv[1]); "
            "sys.modules['streamlit']=None; sys.modules['duckdb']=None; "
            "import ui.kho_hop_dong; assert 'scripts.pipeline.state' not in sys.modules")
    result = subprocess.run([sys.executable, '-P', '-B', '-X', 'utf8', '-c', code,
                              str(ROOT/'apps/retail_app')], cwd=tmp_path, capture_output=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('kind,flag', [('chi_dashboard','--xac-nhan-nguon-moi'),
    ('co_du_lieu_tong_hop','--xac-nhan-tong-hop')])
def test_dashboard_action_uses_exact_record_flag(tmp_path, monkeypatch, kind, flag):
    from types import SimpleNamespace
    from ui import nhap_runner as nr, roles
    rid='b'*24
    monkeypatch.setattr(roles,'current_role',lambda:'admin')
    monkeypatch.setattr(roles,'logged_in_user',lambda:{'username':'admin1'})
    monkeypatch.setattr(roles,'store',lambda:SimpleNamespace(log=lambda *a:None))
    monkeypatch.setattr(nr,'dashboard_state',lambda *a:(tmp_path,{'releases':{rid:{'status':'ready',kind:True}}}))
    calls=[]
    monkeypatch.setattr(nr.subprocess,'run',lambda args,**kwargs:calls.append(args) or SimpleNamespace(returncode=0))
    nr.dashboard_action(SimpleNamespace(base=tmp_path),'duckdb',rid,confirmed=kind=='co_du_lieu_tong_hop')
    assert len(calls)==1 and flag in calls[0]
    assert ('--xac-nhan-tong-hop' in calls[0]) != ('--xac-nhan-nguon-moi' in calls[0])


@pytest.mark.parametrize('both',[False,True])
def test_dashboard_action_rejects_ambiguous_or_unmarked_release(tmp_path,monkeypatch,both):
    from types import SimpleNamespace
    from ui import nhap_runner as nr, roles
    rid='b'*24
    record={'status':'ready'}
    if both:
        record.update(chi_dashboard=True,co_du_lieu_tong_hop=True)
    monkeypatch.setattr(roles,'current_role',lambda:'admin')
    monkeypatch.setattr(roles,'logged_in_user',lambda:{'username':'admin1'})
    monkeypatch.setattr(roles,'store',lambda:SimpleNamespace(log=lambda *a:None))
    monkeypatch.setattr(nr,'dashboard_state',lambda *a:(tmp_path,{'releases':{rid:record}}))
    calls=[]
    monkeypatch.setattr(nr.subprocess,'run',lambda *a,**kw:calls.append(a))
    with pytest.raises(ValueError):
        nr.dashboard_action(SimpleNamespace(base=tmp_path),'duckdb',rid,confirmed=True)
    assert not calls


def test_dashboard_action_keeps_synthetic_confirmation(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from ui import nhap_runner as nr, roles
    rid='b'*24
    monkeypatch.setattr(roles,'current_role',lambda:'admin')
    monkeypatch.setattr(roles,'logged_in_user',lambda:{'username':'admin1'})
    monkeypatch.setattr(roles,'store',lambda:SimpleNamespace(log=lambda *a:None))
    monkeypatch.setattr(nr,'dashboard_state',lambda *a:(tmp_path,{'releases':{rid:{
        'status':'ready','co_du_lieu_tong_hop':True}}}))
    monkeypatch.setattr(nr.subprocess,'run',lambda *a,**kw:pytest.fail('Chưa xác nhận thì không gọi CLI'))
    with pytest.raises(ValueError,match='Cần xác nhận'):
        nr.dashboard_action(SimpleNamespace(base=tmp_path),'duckdb',rid)


@pytest.mark.parametrize('count',[0,1,2])
def test_cloud_command_binds_unique_ready_mot_request(tmp_path,monkeypatch,count):
    import json
    from types import SimpleNamespace
    from ui import roles, nhap_runner as nr
    from ui.nhap_dot import DotStore
    rid='b'*24
    store=DotStore(KhoDia(tmp_path))
    monkeypatch.setattr(roles,'current_role',lambda:'admin')
    monkeypatch.setattr(roles,'logged_in_user',lambda:{'username':'admin1'})
    monkeypatch.setattr(roles,'store',lambda:SimpleNamespace(log=lambda *a:None))
    monkeypatch.setattr(nr,'dashboard_state_cloud',lambda:{'releases':{rid:{
        'status':'ready','chi_dashboard':True}}})
    for index in range(count):
        request_id=MOT if index==0 else MOT.replace('abcdef','abcdee')
        folder=request_path(request_id)
        store.kho.ghi_moi(folder+'/yeu_cau.json',json.dumps({'id':request_id,'loai':'mot_file',
            'file':{'ten':'orders_enriched.csv'}}).encode())
        for target in ('da_gui','dang_doc','da_duyet','cho_chay','dang_chay','da_kiem'):
            store.kho.ghi_json_so_tiep(folder+'/su_kien',{'toi':target,'release_id':rid})
    if count != 1:
        with pytest.raises(ValueError):
            store.dashboard_command(rid)
        assert store.latest_command() is None
    else:
        store.dashboard_command(rid)
        assert store.latest_command()['request_id'] == MOT


def test_dot_replay_keeps_ignoring_mot_only_metadata():
    event={'toi':'da_gui','duong':123,'ly_do':{},'cot_moi':[None],'ten_mo_rong':False}
    assert phat_lai([(1,event)])['trang_thai'] == 'da_gui'
    assert phat_lai([(1,event)],'mot_file')['trang_thai'] == 'hong'


def test_business_signature_exact_json_and_no_mutation():
    import hashlib
    from copy import deepcopy
    from ui.kho_hop_dong import chu_ky_nghiep_vu
    doc={'ten':'orders_enriched','phien_ban':1,'cot':[{'ten':'ghi_chú'}],
         'file':'ui_nhap_cloud/new/data.csv','ngay_duyet':'2026-11-11',
         'duyet_boi':'de','hop_dong_sha256':'old-hash'}
    before=deepcopy(doc)
    expected='{"cot": [{"ten": "ghi_chú"}], "phien_ban": 1, "ten": "orders_enriched"}'
    assert chu_ky_nghiep_vu(doc)==hashlib.sha256(expected.encode('utf-8')).hexdigest()
    assert chu_ky_nghiep_vu(dict(reversed(list(doc.items()))))==chu_ky_nghiep_vu(doc)
    assert doc==before


@pytest.mark.parametrize('key',['file','ngay_duyet','duyet_boi','hop_dong_sha256'])
def test_business_signature_ignores_only_run_metadata(key):
    from ui.kho_hop_dong import chu_ky_nghiep_vu
    doc={'ten':'orders_enriched','phien_ban':1,key:'old'}
    assert chu_ky_nghiep_vu(doc)==chu_ky_nghiep_vu(dict(doc,**{key:'new'}))


def test_business_signature_keeps_version_and_nested_decisions():
    from ui.kho_hop_dong import chu_ky_nghiep_vu
    doc={'ten':'orders_enriched','phien_ban':1,'cot':[{'file':'decision-a'}]}
    assert chu_ky_nghiep_vu(doc)!=chu_ky_nghiep_vu(dict(doc,phien_ban=2))
    assert chu_ky_nghiep_vu(doc)!=chu_ky_nghiep_vu(dict(doc,cot=[{'file':'decision-b'}]))


@pytest.mark.parametrize('signature',['a'*64,None,123])
def test_replay_business_signature_string_only(signature):
    events=[(1,{'toi':'da_gui'}),(2,{'toi':'dang_doc'}),
            (3,{'toi':'da_duyet','chu_ky_nghiep_vu':signature})]
    result=phat_lai(events,'mot_file')
    if isinstance(signature,str):
        assert result['trang_thai']=='da_duyet' and result['chu_ky_nghiep_vu']==signature
    else:
        assert result['trang_thai']=='hong'


# T2b: kiểm cả thao tác ghi và form thật trên trang.
def proposal():
    return {'nguon': {'de_xuat': 'orders'}, 'thuc_the_moi': [],
        'cot': [{'ten_trong_file': 'order_id', 'loai': 'khop'},
                {'ten_trong_file': 'comment', 'loai': 'thuoc_tinh_le', 'nghi_pii': True,
                 'thong_ke': {'so_rong': 0}}]}


@pytest.fixture
def cloud_store(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from ui import roles, nhap_store, nhap_runner, kho_dot
    from ui.nhap_dot import DotStore
    events = []
    monkeypatch.setattr(roles, 'current_role', lambda: 'admin')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'de'})
    monkeypatch.setattr(roles, 'store', lambda: SimpleNamespace(log=lambda *a: events.append(a)))
    monkeypatch.setattr(nhap_store, 'nhap_kha_dung', lambda: False)
    monkeypatch.setenv('RETAIL_NHAP_DOT', 'volume')
    monkeypatch.setenv('RETAIL_BACKEND', 'databricks')
    monkeypatch.setenv('RETAIL_BACKENDS', 'databricks')
    store = DotStore(KhoDia(tmp_path/'volume'))
    monkeypatch.setattr(kho_dot, 'configured_store', lambda: store.kho)
    monkeypatch.setattr(nhap_runner, 'dashboard_state_cloud', lambda: {'releases': {}})
    monkeypatch.setattr(nhap_runner, 'recover_queue', lambda *a, **k: pytest.fail('Không chạy local'))
    store.audit_events = events
    return store


def upload(name='orders_enriched.csv', raw=b'order_id,comment\n1,hello\n'):
    import io
    file = io.BytesIO(raw)
    file.name = name
    return file


def pending_mot(store):
    import yaml
    row = store.gui_mot_file(upload(), 'Bổ sung cột')
    folder = request_path(row['id'])
    store.kho.ghi_moi(folder+'/de_xuat/mapping_de_xuat.yml',
                      yaml.safe_dump(proposal()).encode())
    store.kho.ghi_moi(folder+'/de_xuat/bao_cao_mapping.md', 'BÁO CÁO KHÔNG CÓ MẪU Ô'.encode())
    for target in ('dang_doc', 'cho_duyet'):
        store.kho.ghi_json_so_tiep(folder+'/su_kien', {'toi': target, 'duong':'tay'})
    return store.read(row['id'])


def cloud_page(page):
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(ROOT/'apps/retail_app/views'/f'{page}.py')).run(timeout=20)


def test_single_submit_metadata_hash_permissions_and_visibility(cloud_store, monkeypatch):
    import hashlib
    from ui import roles
    raw=b'order_id,comment\n1,hello\n'
    row=cloud_store.gui_mot_file(upload('../../HELLO.csv',raw),'Mô tả')
    assert row['id'].endswith('_mot') and row['loai']=='mot_file'
    assert row['file']=={'ten':'hello.csv','so_byte':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    assert row['vai_tro']=='admin' and row['trang_thai']=='da_gui'
    assert cloud_store.kho.doc(request_path(row['id'])+'/file/hello.csv')==raw
    assert cloud_store.visible('de','quan_ly')[0]['nhan']=='hello.csv'
    assert cloud_store.visible('other','quan_ly')==[]
    assert cloud_store.visible('other','ky_su')[0]['id']==row['id']
    assert cloud_store.audit_events[-1][1]=='mot_gui'
    monkeypatch.setattr(roles,'current_role',lambda:'khach')
    with pytest.raises(PermissionError):
        cloud_store.gui_mot_file(upload(),'')
    assert len(cloud_store.visible('de','admin'))==1


@pytest.mark.parametrize('case',['missing','type','large'])
def test_single_submit_invalid_upload_leaves_no_request(cloud_store,monkeypatch,case):
    from ui import nhap_dot
    monkeypatch.setattr(nhap_dot,'MAX_FILE_BYTES',10)
    value=None if case=='missing' else upload('bad.exe' if case=='type' else 'data.csv')
    with pytest.raises(ValueError):
        cloud_store.gui_mot_file(value,'')
    assert cloud_store.kho.liet_ke('yeu_cau')==[]


def test_single_failed_metadata_write_never_publishes(cloud_store,monkeypatch):
    original=cloud_store.kho.ghi_moi
    def fail(path,raw):
        if path.endswith('/yeu_cau.json'):
            raise OSError('PRIVATE')
        original(path,raw)
    monkeypatch.setattr(cloud_store.kho,'ghi_moi',fail)
    with pytest.raises(OSError):
        cloud_store.gui_mot_file(upload(),'')
    assert cloud_store.visible('de','admin')==[]


@pytest.mark.parametrize('model',[True,False])
def test_manual_approval_validated_hash_signature_and_model(cloud_store,monkeypatch,model):
    from scripts.ingest import approval
    from ui.kho_hop_dong import load_raw,chu_ky_nghiep_vu
    row=pending_mot(cloud_store)
    monkeypatch.setattr(approval,'has_dbt_model',lambda *a:model)
    name='brand_new'
    result=cloud_store.approve(row['id'],len(row['lich_su']),approval.default_decisions(proposal()),name)
    raw=cloud_store.kho.doc(request_path(row['id'])+'/hop_dong/'+name+'.yml')
    checked=load_raw(name,raw)
    assert checked['file']==f"ui_nhap_cloud/{row['id']}/orders_enriched.csv"
    assert checked['duyet_boi']=='de'
    assert result['trang_thai']==('da_duyet' if model else 'cho_model_dbt')
    assert result['duong']=='tay' and result['ten_mo_rong']==name
    assert result['hop_dong_sha256']==checked['hop_dong_sha256']
    assert result['chu_ky_nghiep_vu']==chu_ky_nghiep_vu(checked)
    assert KhoHopDong(cloud_store.kho).current(name)[0]['phien_ban']==1
    assert any(e[1]=='mot_duyet' for e in cloud_store.audit_events)
    assert cloud_store.kho.liet_ke('lenh')==[]


@pytest.mark.parametrize('case',['invalid','stale','wrong_role'])
def test_manual_approval_rejects_before_writing(cloud_store,monkeypatch,case):
    from scripts.ingest import approval
    from ui import roles
    row=pending_mot(cloud_store)
    decisions=approval.default_decisions(proposal())
    if case=='invalid':
        decisions['khoa_noi']['cot']='missing'
    if case=='wrong_role':
        monkeypatch.setattr(roles,'current_role',lambda:'quan_ly')
    with pytest.raises((ValueError,PermissionError)):
        cloud_store.approve(row['id'],len(row['lich_su'])-(case=='stale'),decisions,'brand_new')
    assert cloud_store.kho.liet_ke(request_path(row['id'])+'/hop_dong')==[]
    assert cloud_store.kho.liet_ke('hop_dong_da_duyet')==[]
    assert cloud_store.read(row['id'])['trang_thai']=='cho_duyet'


def test_manual_existing_contract_stays_unchanged(cloud_store):
    from scripts.ingest import approval
    registry=KhoHopDong(cloud_store.kho)
    before=registry.current('orders_enriched')
    row=pending_mot(cloud_store)
    cloud_store.approve(row['id'],len(row['lich_su']),approval.default_decisions(proposal()),'orders_enriched')
    assert registry.current('orders_enriched')==before
    assert cloud_store.kho.liet_ke('hop_dong_da_duyet')==[]


def test_reject_requires_reason_and_records_audit(cloud_store):
    row=pending_mot(cloud_store)
    with pytest.raises(ValueError):
        cloud_store.reject(row['id'],len(row['lich_su']),' ')
    assert cloud_store.read(row['id'])['trang_thai']=='cho_duyet'
    cloud_store.reject(row['id'],len(row['lich_su']),'Khóa sai')
    assert cloud_store.read(row['id'])['lich_su'][-1]['ghi_chu']=='Khóa sai'
    assert cloud_store.audit_events[-1][1]=='mot_tu_choi'


@pytest.mark.parametrize('target',['cho_chay','huy'])
def test_mot_retry_cancel(cloud_store,target):
    row=pending_mot(cloud_store)
    for state in ('da_duyet','cho_chay','dang_chay','loi'):
        cloud_store.kho.ghi_json_so_tiep(request_path(row['id'])+'/su_kien',{'toi':state})
    cloud_store.change(row['id'],target)
    assert cloud_store.read(row['id'])['trang_thai']==target
    assert cloud_store.audit_events[-1][1]==('mot_chay_lai' if target=='cho_chay' else 'mot_huy')


@pytest.mark.parametrize('state,pending',[
    ('da_gui',True),('dang_doc',True),('da_duyet',True),('het_cho',True),
    ('cho_chay',True),('dang_chay',True),('cho_duyet',False),('cho_model_dbt',False),
    ('khong_moi',False),('da_kiem',False),('tu_choi',False)])
def test_mot_poll_states(state,pending):
    from ui.nhap_dot import can_theo_doi,tao_anh_chup
    assert can_theo_doi(tao_anh_chup([{'id':MOT,'trang_thai':state}],None)) is pending


def auto_mot(store):
    import yaml
    from scripts.ingest.tu_dong import hop_dong_cua_luot
    from ui.kho_hop_dong import load_raw,chu_ky_nghiep_vu
    row=store.gui_mot_file(upload(),'')
    folder=request_path(row['id'])
    meta,approved=KhoHopDong(store.kho).current('orders_enriched')
    prop={'nguon':{'de_xuat':'orders'},'thuc_the_moi':[],
          'cot':[{'ten_trong_file':c,'loai':'khop'} for c in approved['header']]+[
                 {'ten_trong_file':'bonus','loai':'thuoc_tinh_le','nghi_pii':True}]}
    doc=hop_dong_cua_luot(approved,approved['header']+['bonus'],
        f"ui_nhap_cloud/{row['id']}/{row['file']['ten']}",1,'2026-11-11')
    raw=yaml.safe_dump(doc).encode()
    checked=load_raw('orders_enriched',raw)
    store.kho.ghi_moi(folder+'/hop_dong/orders_enriched.yml',raw)
    store.kho.ghi_moi(folder+'/de_xuat/mapping_de_xuat.yml',yaml.safe_dump(prop).encode())
    store.kho.ghi_moi(folder+'/de_xuat/bao_cao_mapping.md',b'Report')
    store.kho.ghi_json_so_tiep(folder+'/su_kien',{'toi':'dang_doc'})
    store.kho.ghi_json_so_tiep(folder+'/su_kien',{'toi':'da_duyet','duong':'tu_dong',
        'ten_mo_rong':'orders_enriched','cot_moi':['bonus'],
        'hop_dong_sha256':checked['hop_dong_sha256'],'chu_ky_nghiep_vu':chu_ky_nghiep_vu(checked)})
    return store.read(row['id'])


def test_upgrade_expected_version_no_backfill(cloud_store):
    row=auto_mot(cloud_store)
    before=cloud_store.read(row['id'])
    decisions=[{'ten':'bonus','xu_ly':'nap','kieu':'integer','duoc_rong':False,'hien_thi':'silver'}]
    result=cloud_store.upgrade_contract(row['id'],decisions,expected=1)
    assert result['phien_ban']==2
    doc=KhoHopDong(cloud_store.kho).current('orders_enriched')[1]
    assert doc['cot'][-1]['tuy_chon'] is True and doc['cot'][-1]['hien_thi']=='silver'
    assert cloud_store.read(row['id'])==before
    assert len(cloud_store.kho.liet_ke('yeu_cau'))==1
    assert cloud_store.kho.liet_ke('lenh')==[]
    assert cloud_store.upgrade_info(row['id']) is None
    with pytest.raises(ValueError):
        cloud_store.upgrade_contract(row['id'],decisions,expected=1)
    assert cloud_store.audit_events[-1][1]=='mot_nang_hop_dong'


@pytest.mark.parametrize('case',['mart','extra','action','version'])
def test_upgrade_invalid_decisions_no_version_write(cloud_store,case):
    row=auto_mot(cloud_store)
    decision={'ten':'bonus','xu_ly':'nap','kieu':'integer','duoc_rong':False,'hien_thi':'silver'}
    if case=='mart':
        decision['hien_thi']='mart'
    if case=='extra':
        decision['ten']='another'
    if case=='action':
        decision['xu_ly']='khoa_noi'
    with pytest.raises(ValueError):
        cloud_store.upgrade_contract(row['id'],[decision],expected=2 if case=='version' else 1)
    assert cloud_store.kho.liet_ke('hop_dong_da_duyet/orders_enriched')==[]


def test_reject_upgrade_and_prevent_repeat(cloud_store):
    row=auto_mot(cloud_store)
    with pytest.raises(ValueError):
        cloud_store.reject_upgrade(row['id'],'',expected=1)
    cloud_store.reject_upgrade(row['id'],'Không cần',expected=1)
    assert KhoHopDong(cloud_store.kho).rejected('orders_enriched',['bonus'])
    assert cloud_store.upgrade_info(row['id']) is None
    assert cloud_store.audit_events[-1][2]['tu_choi'] is True


def test_actual_review_form_approve_with_signature(cloud_store):
    from ui.kho_hop_dong import load_raw,chu_ky_nghiep_vu
    row=pending_mot(cloud_store)
    at=cloud_page('duyet_du_lieu')
    assert not at.exception and not at.error
    assert any('BÁO CÁO' in m.value for m in at.markdown)
    next(b for b in at.button if b.label=='Duyệt').click().run(timeout=20)
    assert not at.exception and not at.error
    result=cloud_store.read(row['id'])
    doc=load_raw('orders_enriched',cloud_store.kho.doc(request_path(row['id'])+'/hop_dong/orders_enriched.yml'))
    assert result['trang_thai']=='da_duyet'
    assert result['chu_ky_nghiep_vu']==chu_ky_nghiep_vu(doc)
    assert not any(b.label=='Chạy' for b in at.button)


def test_actual_review_reject_and_notice(cloud_store):
    import json
    row=pending_mot(cloud_store)
    cloud_store.kho.ghi_moi(request_path(row['id'])+'/thong_bao.json',
                           json.dumps({'thong_bao':'Chờ Admin đưa lên.'}).encode())
    at=cloud_page('duyet_du_lieu')
    assert not at.exception and any('Chờ Admin' in m.value for m in at.info)
    next(t for t in at.text_area if t.label=='Lý do từ chối (bắt buộc)').set_value('Sai nguồn')
    next(b for b in at.button if b.label=='Từ chối').click().run(timeout=20)
    assert not at.exception and not at.error
    assert cloud_store.read(row['id'])['trang_thai']=='tu_choi'
    assert any('Sai nguồn' in w.value for w in at.warning)


def test_actual_upgrade_form_no_backfill_and_notice(cloud_store):
    row=auto_mot(cloud_store)
    at=cloud_page('duyet_du_lieu')
    assert not at.exception and not at.error
    next(b for b in at.button if b.label=='Duyệt nâng hợp đồng').click().run(timeout=20)
    assert not at.exception and not at.error
    assert KhoHopDong(cloud_store.kho).current('orders_enriched')[0]['phien_ban']==2
    assert any('gửi lại file' in i.value for i in at.info)
    assert len(cloud_store.kho.liet_ke('yeu_cau'))==1 and cloud_store.latest_command() is None


def test_actual_send_mixed_list_and_single_submit(cloud_store,monkeypatch):
    import streamlit as st
    from ui import roles
    cloud_store.gui_dot([upload('orders.csv')],'batch','')
    pending_mot(cloud_store)
    at=cloud_page('gui_du_lieu')
    assert not at.exception and not at.error
    assert any('batch' in e.label for e in at.expander)
    assert any('orders_enriched.csv' in e.label for e in at.expander)
    at.radio[0].set_value('Một file dữ liệu mới').run(timeout=20)
    assert not at.exception
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:upload('more.csv'))
    next(b for b in at.button if b.label=='Gửi file dữ liệu mới').click().run(timeout=20)
    assert not at.exception and not at.error
    assert len(cloud_store.visible('de','admin'))==3


@pytest.mark.parametrize('page',['gui_du_lieu','duyet_du_lieu'])
def test_actual_pages_mot_timer_single_read(cloud_store,monkeypatch,page):
    import streamlit as st
    from ui.nhap_dot import DotStore
    auto_mot(cloud_store)
    original=DotStore.visible
    real_fragment=st.fragment
    counts=[]
    intervals=[]
    def visible(self,*args):
        counts.append(args)
        return original(self,*args)
    def fragment(*args,**kwargs):
        intervals.append(kwargs['run_every'])
        return real_fragment(*args,**kwargs)
    monkeypatch.setattr(DotStore,'visible',visible)
    monkeypatch.setattr(st,'fragment',fragment)
    at=cloud_page(page)
    assert not at.exception and not at.error
    assert len(counts)==1 and intervals==['30s']


@pytest.mark.parametrize('kind',['chi_dashboard','co_du_lieu_tong_hop'])
def test_dashboard_ui_type_and_confirmation(cloud_store,monkeypatch,kind):
    from ui import nhap_runner
    rid='b'*24
    row=auto_mot(cloud_store)
    for state in ('cho_chay','dang_chay','da_kiem'):
        cloud_store.kho.ghi_json_so_tiep(request_path(row['id'])+'/su_kien',{'toi':state,'release_id':rid})
    monkeypatch.setattr(nhap_runner,'dashboard_state_cloud',lambda:{'releases':{
        rid:{'status':'ready',kind:True,'nguon_moi':['orders_enriched']}}})
    at=cloud_page('duyet_du_lieu')
    assert not at.exception and not at.error
    assert bool(at.checkbox)==(kind=='co_du_lieu_tong_hop')
    expected='Bản có đợt (dữ liệu tổng hợp)' if kind=='co_du_lieu_tong_hop' else 'Bản có nguồn mới orders_enriched'
    assert expected in [c.value for c in at.caption]
    if at.checkbox:
        at.checkbox[0].check()
    next(b for b in at.button if b.label.startswith('Đưa bản')).click().run(timeout=20)
    assert not at.exception and not at.error
    command=cloud_store.latest_command()
    assert command['release_id']==rid and command['request_id']==row['id']
    assert command['ket_qua'] is None


def test_dashboard_selection_updates_confirmation(cloud_store,monkeypatch):
    from ui import nhap_runner
    monkeypatch.setattr(nhap_runner,'dashboard_state_cloud',lambda:{'releases':{
        'a'*24:{'status':'ready','co_du_lieu_tong_hop':True},
        'b'*24:{'status':'ready','chi_dashboard':True,'nguon_moi':['orders_enriched']}}})
    at=cloud_page('duyet_du_lieu')
    assert at.checkbox and not at.exception
    assert any('Bản có nguồn mới orders_enriched' in option
               for option in at.selectbox(key='cloud_dashboard_release').options)
    at.selectbox(key='cloud_dashboard_release').set_value('b'*24).run(timeout=20)
    assert not at.checkbox and not at.exception
    assert 'Bản có nguồn mới orders_enriched' in [c.value for c in at.caption]


@pytest.mark.parametrize('kind',['chi_dashboard','co_du_lieu_tong_hop','active'])
def test_sidebar_banner_matches_release_kind(monkeypatch,kind):
    from streamlit.testing.v1 import AppTest
    from ui import common,roles
    from dwh import releases
    record={'nguon_moi':['orders_enriched']}
    if kind!='active':
        record[kind]=True
    monkeypatch.setattr(roles,'account_box',lambda *a:None)
    monkeypatch.setattr(releases,'enabled',lambda *a:True)
    monkeypatch.setattr(common,'release_for_read',lambda *a:record)
    at=AppTest.from_string("from ui.common import sidebar\nsidebar('quan_ly')").run()
    assert not at.exception
    assert any('Dữ liệu tổng hợp' in w.value for w in at.warning)==(kind=='co_du_lieu_tong_hop')
    assert any('chưa phải bản chính' in c.value for c in at.caption)==(kind=='chi_dashboard')


def test_cloud_views_and_default_decisions_dependency_boundary(tmp_path):
    # Tiến trình mới: không để import DuckDB từ các test local che hồi quy.
    code=r"""
import ast, importlib.abc, json, os, sys
from pathlib import Path
from types import SimpleNamespace
repo=Path(sys.argv[1])
sys.path[:0]=[str(repo),str(repo/'apps/retail_app')]
forbidden={'duckdb','scripts.ingest.auto_mapping','scripts.ingest.adapters','scripts.pipeline.cli'}
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,*args):
        if fullname in forbidden:
            raise AssertionError('Nạp module bị cấm: '+fullname)
sys.meta_path.insert(0,Deny())
os.environ.update(RETAIL_BACKEND='databricks',RETAIL_BACKENDS='databricks',RETAIL_NHAP_DOT='volume')
from ui import roles,kho_dot,nhap_store,nhap_runner
roles.current_role=lambda:'admin'
roles.logged_in_user=lambda:{'username':'de'}
roles.store=lambda:SimpleNamespace(log=lambda *a:None)
nhap_store.nhap_kha_dung=lambda:False
kho=kho_dot.KhoDia(sys.argv[2])
kho_dot.configured_store=lambda:kho
nhap_runner.dashboard_state_cloud=lambda:{'releases':{}}
from scripts.ingest import approval
proposal={'nguon':{'de_xuat':'orders'},'thuc_the_moi':[],'cot':[{'ten_trong_file':'order_id','loai':'khop'}]}
assert approval.default_decisions(proposal)['khoa_noi']['cot']=='order_id'
assert 'duckdb' not in sys.modules
from ui.nhap_dot import DotStore
import io,yaml
store=DotStore(kho)
f=io.BytesIO(b'order_id\n1\n');f.name='new.csv'
row=store.gui_mot_file(f,'')
folder='yeu_cau/'+row['id']
for target in ('dang_doc','cho_duyet'):
    kho.ghi_json_so_tiep(folder+'/su_kien',{'toi':target})
kho.ghi_moi(folder+'/de_xuat/mapping_de_xuat.yml',yaml.safe_dump(proposal).encode())
kho.ghi_moi(folder+'/de_xuat/bao_cao_mapping.md',b'Report')
from streamlit.testing.v1 import AppTest
for view in ('gui_du_lieu','duyet_du_lieu'):
    at=AppTest.from_file(str(repo/'apps/retail_app/views'/f'{view}.py')).run(timeout=20)
    assert not at.exception and not at.error,(at.exception,at.error)
assert not (forbidden & sys.modules.keys())
# Kiểm import bên ngoài của các module repo thực sự được nạp, gồm đường form.
# Thư viện phụ thuộc của Streamlit do requirements của chính Streamlit quản lý.
import_to_package={'yaml':'pyyaml','databricks.sdk':'databricks-sdk','databricks.sql':'databricks-sql-connector',
                   'psycopg':'psycopg'}
requirements={line.split('==')[0].split('[')[0].strip().lower()
              for line in (repo/'apps/retail_app/requirements.txt').read_text().splitlines()
              if line.strip() and not line.startswith('#')}
roots={'ui','dwh','scripts','views','ai_explain'}
checked=set()
for module in list(sys.modules.values()):
    filename=getattr(module,'__file__',None)
    if not filename:
        continue
    path=Path(filename).resolve()
    if not path.is_relative_to(repo) or path.suffix!='.py':
        continue
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    # Các import nhánh local không chạy không phải phụ thuộc của trang cloud.
    for node in ast.walk(tree):
        names=([n.name for n in node.names] if isinstance(node,ast.Import)
               else [node.module] if isinstance(node,ast.ImportFrom) and node.module else [])
        for name in names:
            top=name.split('.')[0]
            if top in roots or top in sys.stdlib_module_names or name not in sys.modules:
                continue
            package=import_to_package.get(name,import_to_package.get(top,top)).lower()
            assert package in requirements,(str(path),name,package)
            checked.add(package)
assert 'pyyaml' in checked and 'streamlit' in checked
"""
    result=subprocess.run([sys.executable,'-B','-X','utf8','-c',code,str(ROOT),str(tmp_path)],
                          cwd=tmp_path,capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('target,label',[('cho_chay','Chạy lại'),('huy','Hủy')])
def test_actual_review_retry_cancel(cloud_store,target,label):
    row=pending_mot(cloud_store)
    for state in ('da_duyet','cho_chay','dang_chay','loi'):
        cloud_store.kho.ghi_json_so_tiep(request_path(row['id'])+'/su_kien',{'toi':state})
    at=cloud_page('duyet_du_lieu')
    assert not at.exception and not at.error
    next(b for b in at.button if b.label==label).click().run(timeout=20)
    assert not at.exception and not at.error
    assert cloud_store.read(row['id'])['trang_thai']==target


def test_actual_review_no_model_and_invalid_contract(cloud_store):
    row=pending_mot(cloud_store)
    at=cloud_page('duyet_du_lieu')
    next(t for t in at.text_input if t.label=='Tên phần mở rộng').set_value('invalid-name')
    next(b for b in at.button if b.label=='Duyệt').click().run(timeout=20)
    assert not at.exception and at.error
    assert cloud_store.kho.liet_ke(request_path(row['id'])+'/hop_dong')==[]
    next(t for t in at.text_input if t.label=='Tên phần mở rộng').set_value('brand_new')
    next(b for b in at.button if b.label=='Duyệt').click().run(timeout=20)
    assert not at.exception and not at.error
    assert cloud_store.read(row['id'])['trang_thai']=='cho_model_dbt'
    assert any('bổ sung mô hình' in i.value for i in at.info)


def test_actual_review_reject_upgrade_notice(cloud_store):
    row=auto_mot(cloud_store)
    at=cloud_page('duyet_du_lieu')
    next(t for t in at.text_area if t.label=='Lý do từ chối nâng hợp đồng').set_value('Không cần')
    next(b for b in at.button if b.label=='Từ chối nâng hợp đồng').click().run(timeout=20)
    assert not at.exception and not at.error
    assert KhoHopDong(cloud_store.kho).rejected('orders_enriched',['bonus'])
    assert any('Đã từ chối nâng' in i.value for i in at.info)
    assert not any('gửi lại file' in i.value for i in at.info)


@pytest.mark.parametrize('role',['quan_ly','phan_tich','khach'])
def test_mot_review_permission_denied(cloud_store,monkeypatch,role):
    from ui import roles
    row=pending_mot(cloud_store)
    monkeypatch.setattr(roles,'current_role',lambda:role)
    at=cloud_page('duyet_du_lieu')
    assert not at.exception and not at.button
    assert any('không có quyền' in e.value for e in at.error)
    with pytest.raises(PermissionError):
        cloud_store.reject(row['id'],len(row['lich_su']),'Không được')


def test_dashboard_ui_excludes_ambiguous_unmarked_and_not_ready(cloud_store,monkeypatch):
    from ui import nhap_runner
    monkeypatch.setattr(nhap_runner,'dashboard_state_cloud',lambda:{'releases':{
        'a'*24:{'status':'ready','chi_dashboard':True,'co_du_lieu_tong_hop':True},
        'b'*24:{'status':'ready'},
        'c'*24:{'status':'building','chi_dashboard':True}}})
    at=cloud_page('duyet_du_lieu')
    assert not at.exception and not at.error
    assert not any(b.label.startswith('Đưa bản') for b in at.button)


def test_actual_upgrade_conflict_requests_reload(cloud_store,monkeypatch):
    row=auto_mot(cloud_store)
    monkeypatch.setattr(KhoHopDong,'write',lambda *a,**kw: (_ for _ in ()).throw(DaCo('version changed')))
    at=cloud_page('duyet_du_lieu')
    next(b for b in at.button if b.label=='Duyệt nâng hợp đồng').click().run(timeout=20)
    assert not at.exception and not at.error
    assert any('tải lại trang' in w.value for w in at.warning)
    assert cloud_store.kho.liet_ke('hop_dong_da_duyet/orders_enriched')==[]
