"""T2a: trạng thái và kho hợp đồng thuần backend; chưa làm form/trang T2b."""
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
