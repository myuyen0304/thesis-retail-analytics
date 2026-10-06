"""Chứng minh bảng trên app đọc từ DB, không phải số gõ sẵn trong code.

Cách làm: chép warehouse/dbt.duckdb ra file tạm, sửa số thành số "lạ" (không thể trùng số thật), cho app đọc
file tạm. App phải hiện đúng số lạ; đọc file gốc thì vẫn ra số thật. File gốc không bị sửa.
- M0: G/R/N năm 2019 trong bảng năm của trang Tổng quan.
- M1: G/R/R-G toàn kỳ 2012–2022 trên thẻ KPI (tiêu chí nghiệm thu M1).
- M2: giai đoạn và điểm đổi hướng PS2 (plan §3, tiêu chí 5: giai đoạn lấy từ cấu hình BA, không hardcode).
- M3: tháng 8 năm lẻ/chẵn và mức dồn cuối tháng của PS3.
- M4: phần góp N và % đổi số đơn của PS4, tên nhóm, % đóng góp của PS5.
"""
import shutil
from pathlib import Path

import duckdb
import streamlit as st
from streamlit.testing.v1 import AppTest

from dwh.connection import DUCKDB_PATH

APP = Path(__file__).resolve().parents[1] / 'app.py'
LA = {'g': '0,12 tỷ', 'r': '0,10 tỷ', 'n': '4.242'}   # số "lạ" sau khi định dạng (bảng ghi gọn theo tỷ, feedback PM 2026-10-02)


def _dong_2019(monkeypatch, db_path: Path) -> dict:
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(db_path))
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and not at.error
    df = at.dataframe[0].value
    row = df[df['Năm'] == 2019].iloc[0]
    return {'g': row['G (mọi đơn)'], 'r': row['R (đơn đã giao)'], 'n': row['N (số đơn)']}


def _ban_sao(tmp_path: Path, sql: str) -> Path:
    # giữ tên file dbt.duckdb: DuckDB lấy tên file làm tên catalog, và view (vd. rpt_august_parity) trỏ bảng qua "dbt".
    ban_sao = tmp_path / 'dbt.duckdb'
    shutil.copy(DUCKDB_PATH, ban_sao)
    con = duckdb.connect(str(ban_sao))
    con.execute(sql)
    con.close()
    return ban_sao


def _the_kpi_dau(monkeypatch, db_path: Path) -> list[str]:
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(db_path))
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and not at.error
    return [m.value for m in at.metric[:3]] + [m.help.split('Số đầy đủ: ')[1] for m in at.metric[:2]]


def test_sua_so_trong_db_thi_app_doi_theo(monkeypatch, tmp_path):
    ban_sao = _ban_sao(tmp_path, 'update reporting.rpt_revenue_yearly '
                                 'set g = 123456789.01, r = 98765432.10, n = 4242 where year = 2019')

    that = _dong_2019(monkeypatch, DUCKDB_PATH)
    assert that == {'g': '1,14 tỷ', 'r': '0,86 tỷ', 'n': '33.259'}   # số thật (1.136.801.441,51; 864.329.801,94), làm tròn
    assert _dong_2019(monkeypatch, ban_sao) == LA                                      # app hiện đúng số đã sửa


def test_sua_so_toan_ky_thi_the_kpi_doi_theo(monkeypatch, tmp_path):
    ban_sao = _ban_sao(tmp_path, "update reporting.rpt_revenue_total "
                                 "set g = 111111111.11, r = 22222222.22, capture_rate = 0.4321 where period_code = '2012-2022'")
    assert _the_kpi_dau(monkeypatch, DUCKDB_PATH) == ['16,43 tỷ', '12,52 tỷ', '76,2%', '16.430.476.585,53.', '12.518.175.957,20.']
    assert _the_kpi_dau(monkeypatch, ban_sao) == ['0,11 tỷ', '0,02 tỷ', '43,2%', '111.111.111,11.', '22.222.222,22.']


def _ps2(monkeypatch, db_path: Path):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(db_path))
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.switch_page('views/ps2_xu_huong.py').run()
    assert not at.exception and not at.error
    return at


def test_sua_giai_doan_thi_ps2_doi_theo(monkeypatch, tmp_path):
    ban_sao = _ban_sao(tmp_path, "update reporting.rpt_revenue_phase set phase_name = 'Thử', cagr = 0.4242 "
                                 "where phase_code = 'A'; "
                                 "update reporting.rpt_revenue_turning_point set magnitude = -0.1234, turn_note = 'ghi thử' "
                                 "where turning_year = 2016")
    that = _ps2(monkeypatch, DUCKDB_PATH)
    assert (that.metric[0].label, that.metric[0].value) == ('A. Tăng trưởng', '+8,75%')
    sua = _ps2(monkeypatch, ban_sao)
    assert (sua.metric[0].label, sua.metric[0].value) == ('A. Thử', '+42,42%')
    td = sua.dataframe[2].value
    assert td['Độ lớn'].tolist()[0] == '−12,3%' and td['Ghi chú của BA'].tolist()[0] == 'ghi thử'


def test_sua_so_thi_ps3_doi_theo(monkeypatch, tmp_path):
    # rpt_august_parity là view trên rpt_revenue_monthly: sửa chỉ số tháng 8/2013 thì chênh lẻ/chẵn tính lại theo
    ban_sao = _ban_sao(tmp_path, "update reporting.rpt_revenue_monthly set month_index = 2.5 "
                                 "where month_start_date = date '2013-08-01'; "
                                 "update reporting.rpt_revenue_total set eom_excess = 0.1234 where is_analysis_period; "
                                 "update reporting.rpt_revenue_yearly set ps2_phase_codes = 'X' where year = 2014; "
                                 "update reporting.rpt_calendar_stability set metric_value = 9.87 "
                                 "where rhythm_code = 'mua_vu'")

    def the(db_path):
        monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
        monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(db_path))
        st.cache_data.clear()
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        at.switch_page('views/ps3_nhip_lich.py').run()
        assert not at.exception and not at.error
        return [m.value for m in at.metric], ' '.join(c.value for c in at.caption), at.dataframe[2].value   # bảng theo năm

    that, cap_that, tb_that = the(DUCKDB_PATH)
    assert tb_that['Giai đoạn'].tolist()[1] == 'A'
    assert that == ['−37,7%', '3,39 lần', '+7,2 điểm %']
    assert 'năm lẻ nào cũng thấp hơn mọi năm chẵn' in cap_that
    sua, cap_sua, tb_sua = the(ban_sao)
    assert tb_sua['Giai đoạn'].tolist()[1] == 'X'
    # năm lẻ: (0,8317 × 5 − 0,8849 + 2,5) / 5 = 1,1547; ÷ 1,3341 − 1 = −13,4%
    assert sua == ['−13,4%', '9,87 lần', '+12,3 điểm %']
    assert 'có năm lẻ cao hơn năm chẵn' in cap_sua


def test_sua_thang_doi_huong_thi_ps2_doi_theo(monkeypatch, tmp_path):
    ban_sao = _ban_sao(tmp_path, "update reporting.rpt_revenue_direction_change "
                                 "set change_month_date = date '2019-03-01', months_held = 42 "
                                 "where window_months = 6 and direction_after = 'xuong'")
    assert _ps2(monkeypatch, DUCKDB_PATH).dataframe[0].value['Tháng phát hiện'].tolist()[2] == '02/2017'
    tc = _ps2(monkeypatch, ban_sao).dataframe[0].value
    assert (tc['Tháng phát hiện'].tolist()[2], tc['Hướng mới giữ'].tolist()[2]) == ('03/2019', '42 tháng')

def test_sua_phan_gop_va_nhom_thi_ps4_ps5_doi_theo(monkeypatch, tmp_path):
    ban_sao = _ban_sao(tmp_path, "update reporting.rpt_driver_period set contrib_n = -123456789, n_change_rate = -0.1234 "
                                 "where period_code = '2019'; "
                                 "update reporting.rpt_revenue_segment_yearly set dimension_value = 'ThuNghiem', "
                                 "contribution_to_delta = 0.4242 where dimension_value = 'Streetwear' and year = 2019")

    def trang(db_path, page):
        monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
        monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(db_path))
        st.cache_data.clear()
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        at.switch_page(page).run()
        assert not at.exception and not at.error
        return at

    the_n = trang(DUCKDB_PATH, 'views/ps4_don_mon_gia.py').metric[1]
    assert (the_n.value, the_n.proto.delta) == ('−572,4 triệu', '−40,3%')
    the_n = trang(ban_sao, 'views/ps4_don_mon_gia.py').metric[1]
    assert (the_n.value, the_n.proto.delta) == ('−123,5 triệu', '−12,3%')
    that = trang(DUCKDB_PATH, 'views/ps5_nhom.py')
    assert that.metric[2].value == 'Streetwear'
    sua = trang(ban_sao, 'views/ps5_nhom.py')
    assert sua.metric[2].value == 'ThuNghiem'
    assert sua.dataframe[0].value.set_index('Nhóm').loc['ThuNghiem', '% đóng góp vào mức đổi tổng'] == '42,4%'
