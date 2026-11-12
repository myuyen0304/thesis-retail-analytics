"""Form duyệt dùng chung cho yêu cầu local và Volume; không đọc dữ liệu nguồn."""
import pandas as pd
import streamlit as st

from scripts.ingest import approval
from scripts.ingest.source_contract import SOURCES


def form_duyet(proposal, filename, request_id):
    import yaml
    from scripts.ingest import extension_contract
    defaults = approval.default_decisions(proposal)
    with st.form('duyet_' + request_id):
        name = st.text_input('Tên phần mở rộng', approval.extension_name(filename))
        st.caption('Duyệt tay cho tên đã có hợp đồng chỉ áp dụng với yêu cầu này; hợp đồng hiện hành chỉ đổi qua Nâng hợp đồng.')
        st.caption('PII mặc định chỉ ở silver. Chọn mart là quyết định chủ động cho phép xuất hiện trên báo cáo.')
        frame = pd.DataFrame(defaults['cot'])
        for col, value in [('kieu', 'string'), ('duoc_rong', False), ('hien_thi', 'silver'), ('ly_do', '')]:
            if col not in frame:
                frame[col] = value
            frame[col] = frame[col].fillna(value)
        edited = st.data_editor(frame, disabled=['ten'], hide_index=True, key='cot_' + request_id,
            column_config={'xu_ly': st.column_config.SelectboxColumn('Xử lý', options=['khoa_noi', 'doi_chieu_loi', 'bo', 'nap'], required=True),
                           'kieu': st.column_config.SelectboxColumn('Kiểu', options=extension_contract.VALID_TYPES, required=True),
                           'duoc_rong': st.column_config.CheckboxColumn('Được rỗng'),
                           'hien_thi': st.column_config.SelectboxColumn('Hiển thị', options=['silver', 'mart']),
                           'ly_do': st.column_config.TextColumn('Lý do')})
        source = st.selectbox('Nguồn nối', list(SOURCES), index=list(SOURCES).index(defaults['khoa_noi']['nguon']) if defaults['khoa_noi']['nguon'] in SOURCES else 0)
        source_key = st.text_input('Cột khóa trong nguồn', defaults['khoa_noi']['cot_nguon'])
        entities = st.text_area('Thực thể đã duyệt (YAML; [] nếu không duyệt thực thể)',
            yaml.safe_dump(defaults['thuc_the'], allow_unicode=True, sort_keys=False), height=180)
        tolerance = st.number_input('Ngưỡng cách ly (tỷ lệ)', min_value=0.0, max_value=0.99, value=0.01, step=0.01)
        approve = st.form_submit_button('Duyệt', type='primary')
    if not approve:
        return None
    try:
        cols = []
        for row in edited.to_dict('records'):
            fields = ['ten', 'xu_ly']
            if row['xu_ly'] in ('nap', 'khoa_noi'):
                fields += ['kieu', 'duoc_rong']
            if row['xu_ly'] == 'nap':
                fields += ['hien_thi']
            if row['xu_ly'] == 'bo':
                fields += ['ly_do']
            cols.append({k: row[k] for k in fields})
        decisions = {'cot': cols, 'thuc_the': yaml.safe_load(entities), 'nguong_cach_ly': tolerance,
                     'khoa_noi': {'nguon': source, 'cot_nguon': source_key,
                        'cot': next((r['ten'] for r in cols if r['xu_ly'] == 'khoa_noi'), '')}}
        return name, decisions
    except Exception as error:
        st.error('Quyết định chưa hợp lệ: ' + type(error).__name__)
        return None


def form_nang(proposal, columns, request_id):
    """Chỉ lấy quyết định về cột mới; mặc định silver để bảo vệ PII."""
    from scripts.ingest import extension_contract
    defaults = [c for c in approval.default_decisions(proposal)['cot'] if c['ten'] in columns]
    for column in defaults:
        if column['xu_ly'] == 'nap':
            column['hien_thi'] = 'silver'
    st.caption('Chỉ các cột mới; mặc định silver. Chọn mart chỉ khi model dbt đã có cột đó.')
    with st.form('nang_' + request_id):
        frame = pd.DataFrame(defaults)
        for col, value in [('kieu', 'string'), ('duoc_rong', False), ('hien_thi', 'silver'), ('ly_do', '')]:
            if col not in frame:
                frame[col] = value
            frame[col] = frame[col].fillna(value)
        edited = st.data_editor(frame, disabled=['ten'], hide_index=True, key='cot_nang_' + request_id,
            column_config={'xu_ly': st.column_config.SelectboxColumn('Xử lý', options=['bo', 'nap'], required=True),
                           'kieu': st.column_config.SelectboxColumn('Kiểu', options=extension_contract.VALID_TYPES, required=True),
                           'duoc_rong': st.column_config.CheckboxColumn('Được rỗng'),
                           'hien_thi': st.column_config.SelectboxColumn('Hiển thị', options=['silver', 'mart']),
                           'ly_do': st.column_config.TextColumn('Lý do')})
        approve = st.form_submit_button('Duyệt nâng hợp đồng')
    if not approve:
        return None
    return [{key: row[key] for key in
             (['ten', 'xu_ly', 'kieu', 'duoc_rong', 'hien_thi'] if row['xu_ly'] == 'nap'
              else ['ten', 'xu_ly', 'ly_do'])} for row in edited.to_dict('records')]
