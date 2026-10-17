# Ghi chú: hoàn thành L2 deep link, Airflow chạy Databricks, rollback trên Databricks (2026-10-17)

PM giao ngày 2026-10-17: hoàn thành ba việc còn dở trên sơ đồ `docs/references/kien_truc_pipeline_tong.png`, làm đến đâu
ghi đến đó, rồi nhờ Astra kiểm lại. File này ghi theo thứ tự làm. Mỗi mục có: đã làm gì, lệnh, kết quả, cách kiểm lại, phần chưa kiểm.

PM chốt trước khi chạy cloud (2026-10-17, trả lời câu hỏi của Claude):
- commit code deep link, mỗi file một commit; PM tự push và Reboot bản public;
- chạy Airflow Docker với target Databricks rồi thử rollback; bản public đổi bản phục vụ 3 lần và **kết thúc ở bản mới**.

## 1. L2: nút mở trang kèm bộ lọc (deep link)

**Trạng thái:** code xong ở local, test đạt. Chưa kiểm trên bản public (cần PM push và Reboot, xem mục 1.4).

### 1.1 Thiết kế

- Link do **app** dựng từ tham số của lời gọi tool đã `ok` trong lượt (`apps/retail_app/ai_explain/links.py`), không lấy từ
  câu văn của mô hình. Không thêm tool, không sửa prompt: trường hợp xấu nhất của prompt đang 199.629 / 200k token.
- Chỉ hiện khi câu trả lời qua bước kiểm (`ok`), cùng luật với biểu đồ. Rerun vẽ lại từ lượt đã lưu, không gọi lại mô hình.
- Trang mở bằng query params, chọn sẵn bộ lọc. Hàm `ui.common.url_choice`: giá trị có trong danh sách thì chọn; không có tham số
  thì giữ mặc định; giá trị lạ thì báo `st.info` và dùng mặc định, trang không văng lỗi.
- Bảng ánh xạ:

| Tool (đã `ok`) | Trang | Query params | Không có link khi |
|---|---|---|---|
| `get_segment_contribution` | PS5 | `chieu`, `nam` | metric G (trang chỉ có R) |
| `get_revenue_drivers` | PS4 | `ky` = năm | metric G, hoặc `period_type = phase` |
| `get_revenue_summary` | PS1 | `ky` = năm | có `to_year` khác `year` (chuỗi nhiều năm) |
| `get_revenue_monthly` | PS1 | `ky` = năm (bảng tháng của năm có tháng được hỏi) | |
| `get_revenue_gap` | PS1 | `ky` = năm, hoặc `2013-2022` | |
| `get_revenue_trend` | PS2 | không (trang không có bộ lọc) | |
| `get_calendar_pattern` | PS3 | không (trang không có bộ lọc) | |
| `get_forecast` | Dự báo | không (trang chỉ vẽ model chính, cả kỳ) | model không phải model chính (`derived.selected_is_primary` sai) |
| `get_forecast_backtest` | Dự báo | không (bảng so sánh có mọi ứng viên) | |
| `get_metric_definition` | | | luôn: không có trang tương ứng |

Hôm nay catalog trả `unsupported` cho segment G, drivers G và drivers theo giai đoạn. Ba luật chặn ở cột cuối là để nếu sau này
catalog mở thì link vẫn không trỏ sang trang chỉ có R.

Phần hẹp hơn mà trang vẫn hiện đủ thì ghi trong nhãn nút: một tháng nằm trong bảng tháng của năm, một nhóm nằm trong bảng các
nhóm. Dưới các nút có dòng: trang đọc bản dữ liệu **đang phục vụ lúc mở trang**, có thể khác bản mà câu trả lời đã ghim nếu
pipeline vừa công bố bản mới.

### 1.2 File đổi

- Mới: `apps/retail_app/ai_explain/links.py`, `apps/retail_app/tests/test_ai_links.py`.
- Sửa: `apps/retail_app/ui/common.py` (thêm `url_choice`), `apps/retail_app/views/ps1_do_dung.py`, `ps4_don_mon_gia.py`,
  `ps5_nhom.py` (đọc query params), `apps/retail_app/views/ai_explain.py` (hiện nút `st.page_link`).

### 1.3 Kiểm (local DuckDB, provider giả, không gọi LLM)

- `cd apps/retail_app; ../../.venv/Scripts/python.exe -m pytest tests/test_ai_links.py -q` → **26 passed**. Gồm:
  - 9 ánh xạ tool → (trang, query params), chạy qua `service.run_turn` thật trên DuckDB;
  - 5 ca không có link: chuỗi nhiều năm, tool không có trang, ba tổ hợp catalog chưa mở;
  - tool lỗi thì không có link, link trùng thì gộp;
  - dự báo: model chính có link, `sarimax_full` thì không;
  - **đối chứng ở phía trang:** mở trang bằng đúng query params của link (AppTest), rồi đọc widget của chính trang. PS5
    region / 2016, PS4 2021, PS1 2013-2022, PS1 2014 đều được chọn sẵn đúng;
  - không có tham số thì giữ mặc định (category / 2019); 3 bộ tham số lạ thì báo và dùng mặc định;
  - trang chat: nút trỏ trang `ps5_nhom` với `chieu=region&nam=2019`, rerun không gọi lại mô hình; câu trả lời bị chặn thì
    không có nút.
- **Thử phá** (sửa tạm code rồi trả lại):
  - PS5 bỏ đọc `?nam` → 3 test trượt;
  - bỏ điều kiện model chính → 1 test trượt;
  - hiện nút cả khi câu trả lời bị chặn → 1 test trượt.
  Trả code lại thì 26/26 đạt.
- Hồi quy toàn bộ test app (`cd apps/retail_app; ../../.venv/Scripts/python.exe -m pytest tests -q`): **876 passed,
  110 skipped** (các test cần Databricks), 0 failed, 10 phút 15 giây. Lần trước là 850 passed; thêm đúng 26 test mới.
- Commit, mỗi file một commit, trên nhánh `app/myuyen`: `22677c0` (`ui/common.py`), `fb69dc3` (PS1), `279e980` (PS4),
  `49161a8` (PS5), `1e44e11` (`links.py`), `f621a41` (trang chat), `532b240` (test). Chưa push: PM tự push.
- **Lưu ý cho người kiểm:** lúc 20:18, trong khi hồi quy đang chạy, có người / agent khác sửa
  `apps/retail_app/ai_explain/evidence.py` và `apps/retail_app/tests/test_ai_forecast.py` ("RV12 lượt kiểm Codex 2026-10-17").
  Hai file này **không** thuộc việc này, không được commit ở đây và vẫn đang ở trạng thái chưa commit. Hồi quy nhiều khả năng dùng code đã commit, vì pytest nạp module lúc bắt đầu chạy (trước 20:18). Đây là suy luận, xem mục 5.

### 1.4 Chưa kiểm

- Bản public: cần PM push rồi Reboot. Câu thử đề xuất:
  - "Khu vực nào kéo giảm R năm 2019?": dưới câu trả lời có nút "Mở trang PS5: Nhóm kéo lên/xuống · khu vực, năm 2019". Bấm thì
    trang PS5 mở với chiều Khu vực, năm 2019;
  - "Vẽ R từng năm 2013–2022": có biểu đồ, không có nút (chuỗi nhiều năm, đúng luật).
- Chưa chụp ảnh trang chat có nút.

## 2. Airflow Docker chạy target Databricks

**Trạng thái:** **đạt** 2026-10-17. DAG `retail_batch_pipeline`, run Airflow `dbx-airflow-20261017-01`, 4/4 task `success`, công bố release `b25b3e471bae45768a79e4a2`. App và chat đọc đúng bản mới (mục 2.3).

### 2.1 Chuẩn bị

- **Image dựng từ đúng commit, không từ thư mục làm việc.** Thư mục làm việc đang có hai file sửa dở của người khác (mục 1.3).
  Vì vậy xuất sạch commit `532b240` bằng `git archive 532b240 apps/retail_app scripts retail_dbt deploy` vào thư mục tạm, rồi
  `docker build -f deploy/airflow/Dockerfile -t retail-airflow:local <thư mục tạm>`. Image `45835b3d3866`.
- Trong image: `code_version()` = `660b2affa0a0cab70095ae5f581a13c39053303c93b6ce6d2ebd6742a1f466f1`, bằng đúng
  `code_version` tính trên bản xuất của `532b240`; có `ai_explain/links.py`; dbt có cả adapter duckdb 1.11.0 và
  databricks 1.12.6.
- `.env.airflow.local` có đủ biến writer, reader APP, reader AI (chỉ kiểm có / trống, không in giá trị).
  `RETAIL_PIPELINE_SCHEDULE_ENABLED=false`: DAG không có lịch, chỉ chạy khi kích hoạt tay.
- **Mốc trước khi đổi bản** (script `kiem_sau_doi_ban.py`, dựng lại môi trường của bản public: chỉ có secrets của
  `.env.streamlit_cloud.local`, chế độ versioned, app đọc bằng SP `retail-web-ro`, chat chạy trọn một lượt `service.run_turn`
  bằng SP `retail-ai-ro` với provider giả):
  - app đọc bản `cfe19211211e420abdfcabb3`: R 2019 = 864.329.801,94; G dự báo 08/2023 = 74.151.832,38 (31 ngày, `lgbm_full / direct`);
  - chat: câu dự báo 08/2023 `ok`, 74.151.832 VND; câu R 2019 `ok`, 864.329.802 VND; `release_id` trong bằng chứng của cả hai câu là
    `cfe19211211e420abdfcabb3`.

  Script này cũng đóng mục "chưa kiểm `release_id` trong phần Bằng chứng" (ở mức code, chưa qua giao diện public).

### 2.2 Chạy

- `docker compose -f docker-compose.airflow.yml up -d airflow-api airflow-scheduler airflow-dag-processor`. Cả ba container chạy
  image `45835b3d3866`.
- 20:25:25, kích hoạt tay: `airflow dags trigger retail_batch_pipeline --run-id dbx-airflow-20261017-01 --conf
  '{"target": "databricks"}'`. Mã run của pipeline là 24 ký tự đầu SHA-256 của run Airflow: `de80c263dce23aec44d70c44`.
  Thư mục: `warehouse/pipeline/docker/runs/de80c263dce23aec44d70c44/`.
- Writer: root `warehouse/pipeline/docker` (lock riêng của Airflow). Lần chạy CLI sáng nay dùng root `warehouse/pipeline`.
  Hai lần không chạy cùng lúc, và registry trên cloud có compare-and-swap (`expected_active` = `cfe19211…`).
- `prepare_snapshot` đạt (20:25 → 20:26). `ingest_and_dbt_build` bắt đầu 20:26:45.
- PM thấy dòng `ERROR … statsmodels … ConvergenceWarning … mlefit = super().fit(` trong log Airflow lúc 20:28. Đây không phải lỗi
  task: Airflow gắn mức "error" cho mọi dòng chương trình con in ra stderr (logger `task.stderr`). Nguồn là cảnh báo của statsmodels
  khi lần fit SARIMAX đầu bằng L-BFGS chưa hội tụ. `scripts/forecast/core.py` (khoảng dòng 249) khi đó tự fit lại (Powell, rồi L-BFGS),
  và stage chỉ dừng nếu fit cuối vẫn không hội tụ (`check_convergence`). Lần chạy CLI sáng nay cũng in đúng 2 cảnh báo này
  (`forecast_meta.json`: 32 lần fit, 2 lần fit lại) và vẫn đạt.

### 2.3 Kết quả

| Task | Bắt đầu | Kết thúc | Thời gian |
|---|---|---|---|
| `prepare_snapshot` | 20:25:24 | 20:26:44 | 1 phút 20 giây |
| `ingest_and_dbt_build` | 20:26:45 | 20:40:19 | 13 phút 34 giây (stage dự báo 321 giây) |
| `quality_and_reader_gate` | 20:40:20 | 20:46:36 | 6 phút 16 giây |
| `publish_release` | 20:46:37 | 20:47:58 | 1 phút 21 giây |

Giờ Việt Nam; tổng 22 phút 34 giây. Lần chạy CLI trên Windows sáng nay mất khoảng 33 phút; stage dự báo khi đó mất 747 giây.

- `context.json` (`warehouse/pipeline/docker/runs/de80c263dce23aec44d70c44/`):
  - release `b25b3e471bae45768a79e4a2`, snapshot `5bd9a84aaf73` (cùng snapshot với bản sáng nay);
  - `code_version` `660b2aff…`, tức commit `532b240`;
  - `expected_active` `cfe19211211e420abdfcabb3`, `stage` `published`; không có `failure.json`.
- Quality gate:
  - G / COGS 3.833 ngày khớp `sales.parquet` của snapshot;
  - 36 relation marts / reporting so từng dòng giữa Databricks và DuckDB đối chứng: `cloud_parity: true`;
  - cấp quyền và thử đọc bằng chính SP app và SP AI đạt.
- dbt (`run_results.json`): 222 node trên DuckDB đối chứng và 222 node trên Databricks, mỗi bên 62 `success` và 160 `pass`.
- Dự báo:
  - model chính `lgbm_full / direct`, chọn ở bước 2 của luật (điểm thấp nhất);
  - `model_version` `3ac33fc83143`, như bản `cfe19211…`;
  - 32 lần fit, 1 lần phải fit lại.
- **Kiểm sau khi công bố** (`kiem_sau_doi_ban.py b25b3e471bae45768a79e4a2`):
  - code lấy từ bản xuất sạch của `532b240` (`KIEM_CODE_ROOT`), để không dính hai file đang sửa dở;
  - app (SP `retail-web-ro`) đọc bản `b25b3e47…`: R 2019 = 864.329.801,94; G dự báo 08/2023 = 74.151.832,38;
  - chat (SP `retail-ai-ro`, một lượt trọn vẹn): câu dự báo `ok`, 74.151.832 VND; câu R 2019 `ok`, 864.329.802 VND;
    `release_id` trong bằng chứng là `b25b3e47…`;
  - **ĐẠT**.
- **So hai bộ dự báo** (`forecast_daily` / `forecast_backtest` parquet của `runs/dbx-20261017-01` và `docker/runs/de80c263…`; 8.220 / 546 dòng, ghép đủ theo khóa):
  - model chính `lgbm_full / direct`: G và COGS dự báo theo ngày **trùng** (lệch tối đa ~2e-9, sai số làm tròn số thực);
  - khoảng 80% của model chính: cận dưới lệch tối đa 11.194 VND, cận trên 5.965 VND một ngày (tương đối ≤ 0,3%);
  - model khác: `sarimax_2019` lệch tối đa 0,016%; các model còn lại ≤ 1e-7;
  - backtest: thứ hạng ứng viên và `is_primary` giống nhau; các chỉ số lệch tối đa 1,03% (`cogs_g_t8_du_bao` của `lgbm_full`).
    Điểm ngày kết hợp của model chính 577.160 → 576.790 (−0,06%); MAPE G tháng 11,399% → 11,425% (cả hai hiện "11,4%").
  - Lần so Docker với Windows ngày 2026-10-15 ghi lệch backtest tối đa 0,15%; lần này lớn hơn (1,03%) nhưng không đổi model chính
    hay dự báo điểm. Chưa tìm nguyên nhân (khác hệ điều hành / số luồng). Vì vậy trang Dự báo của bản `b25b3e47…` có thể hiện
    điểm backtest và cận khoảng khác bản `cfe19211…` ở chữ số nhỏ.
- Bản public (chế độ versioned) tự đọc bản mới từ lúc publish (20:47:58). Không cần Reboot: app đọc registry mỗi lần chạy trang.
- Script kiểm: `warehouse/pipeline/kiem_sau_doi_ban.py` (thư mục bị gitignore, không vào git).
  Chạy lại: `KIEM_CODE_ROOT=<thư mục code> .venv/Scripts/python.exe warehouse/pipeline/kiem_sau_doi_ban.py <release_id mong đợi>`.

### 2.4 Chưa làm

- Chưa bật lịch chạy hằng ngày: `RETAIL_PIPELINE_SCHEDULE_ENABLED` vẫn là `false`, DAG chỉ chạy khi kích hoạt tay.
- Chưa gửi cảnh báo email / Slack khi task lỗi (như cũ).

## 3. Rollback trên Databricks

**Trạng thái:** **đạt** 2026-10-17. Cả ba lần đổi bản phục vụ trên cloud đều kiểm bằng app và chat. Chạy lại cùng lệnh rollback
thì registry không đổi. Mã bản không có trong registry thì bị từ chối. Bản đang phục vụ cuối cùng: `b25b3e471bae45768a79e4a2`,
theo lựa chọn của PM.

### 3.1 Lệnh

Chạy trong container Airflow, cùng image, cùng biến môi trường writer, cùng root và writer lock với DAG
(`warehouse/pipeline/docker`). Không có DAG run nào chạy cùng lúc.

```
docker exec -w /opt/retail retail-analytics-airflow-scheduler-1 /opt/pipeline/bin/python -m scripts.pipeline.cli   rollback --run-id <run-id> --release-id <24 hex> --target databricks --root warehouse/pipeline/docker
```

Rollback gọi `verify_consumers` của bản đích: cấp lại quyền đọc cho SP app / AI, rồi thử đọc bằng chính hai SP đó, kể cả kiểm
quyền thừa. Sau đó nó đổi con trỏ `active` bằng compare-and-swap và ghi `rollbacks/<uuid>.json`.
Đọc registry: `warehouse/pipeline/doc_registry.py` (chép vào container rồi chạy bằng writer, chỉ in version / active / danh sách
release): `docker cp warehouse/pipeline/doc_registry.py retail-analytics-airflow-scheduler-1:/tmp/doc_registry.py`, rồi
`docker exec -w /opt/retail -e PYTHONPATH=/opt/retail retail-analytics-airflow-scheduler-1 /opt/pipeline/bin/python /tmp/doc_registry.py`.

### 3.2 Kết quả từng bước

| Giờ | Việc | Kết quả | Registry sau đó |
|---|---|---|---|
| 20:47:58 | DAG publish bản mới | `active` = `b25b3e47…` | (không đọc version) |
| 20:50:50 → 20:52:16 | `rollback-dbx-20261017-01` về `cfe19211…` | exit 0, "Đã khôi phục phiên bản cfe19211…"; `rollbacks/eec91757….json` ghi from `b25b3e47…` to `cfe19211…` | version `ee413138…`, active `cfe19211…` |
| 20:52 | kiểm app + chat (`kiem_sau_doi_ban.py cfe19211…`) | **ĐẠT**: app đọc `cfe19211…`; chat 2 câu `ok`, `release_id` trong bằng chứng `cfe19211…`; số như cũ | |
| kết thúc 20:55:06 | `rollback-dbx-20261017-02`: **chạy lại** cùng lệnh về `cfe19211…` | exit 0 | version **vẫn** `ee413138…`: không ghi gì (`Registry.publish` trả về ngay khi bản đích đã là active) |
| 20:55 | ca âm `rollback-dbx-20261017-am`, mã `0123456789abcdef01234567` (không có trong registry) | bị từ chối, nhưng báo `KeyError` thô, exit 1 (xem 3.3) | version vẫn `ee413138…` |
| 20:55:52 | `rollback-dbx-20261017-03` về lại `b25b3e47…` | exit 0 | version `5c754d80…`, active `b25b3e47…` |
| 20:58 | kiểm app + chat (`kiem_sau_doi_ban.py b25b3e47…`) | **ĐẠT**: app đọc `b25b3e47…`; chat 2 câu `ok`, `release_id` trong bằng chứng `b25b3e47…` | |

Ở cả ba lần đổi, hai số kiểm được không đổi (cùng snapshot `5bd9a84aaf73`; phần khác nhỏ của backtest / khoảng dự báo: mục 2.3):
- R 2019 = 864.329.801,94 (chat hiện 864.329.802 VND);
- G dự báo 08/2023 = 74.151.832,38 (chat hiện 74.151.832 VND), 31 ngày, `lgbm_full / direct`.

Bản public (versioned) đọc registry mỗi lần chạy trang, nên tự theo con trỏ, không cần Reboot. Trong lúc thử (20:47 → 20:56),
người mở app có thể đã thấy mã bản đổi qua lại trong phần Bằng chứng; số PS và dự báo điểm không đổi, điểm backtest / cận khoảng dự báo trên trang Dự báo lệch ở chữ số nhỏ (mục 2.3).

### 3.3 Phát hiện, đã sửa sau đó

- **Rollback về mã bản không có trong registry:** lệnh vẫn từ chối đúng và không ghi gì. Nhưng nó báo bằng traceback `KeyError`,
  exit 1, trong khi quy ước của CLI là sai hợp đồng thì exit 2 kèm câu báo rõ (`main()` chỉ bắt `ValueError` /
  `FileNotFoundError`). Trong Airflow, exit 1 bị coi là "lỗi tạm thời" và sẽ retry. Hiện rollback không chạy qua DAG nên chưa gây
  hại. Sửa đề xuất, một dòng: kiểm `release_id` có trong `state['releases']` trước, không có thì `ValueError`. Chờ PM quyết.
- **Đã sửa** (PM đồng ý, tối 2026-10-17): `2c067ac` kiểm mã bản trước khi đọc record, không có thì `ap.error` giống lỗi định
  dạng mã ngay trên: in câu "không có phiên bản … trong registry; các bản rollback được: …", exit 2. Test `b5aa37c`: registry
  có bản `a…`, rollback về `b…` → exit 2, câu báo nêu cả hai mã, registry và thư mục `rollbacks/` không đổi. Test này trượt
  với `KeyError` trước khi sửa. `scripts/pipeline/tests` 16/16. Thử CLI thật trên một registry tạm ở máy: đúng câu báo, exit 2.
  **Chưa chạy lại trên Databricks.** Lưu ý: `scripts/pipeline` nằm trong `code_version`, nên lần chạy pipeline sau sẽ dựng bản mới
  thay vì coi là không đổi.

### 3.4 Chưa kiểm

- **Gate lỗi trên cloud thì giữ bản đang phục vụ:** chưa cố ý làm hỏng một lần chạy trên Databricks. Phần này mới được chứng minh
  bằng test local: `scripts/pipeline/tests` (publish khi chưa đạt, CAS, retry) và lần nghiệm thu local 2026-10-11/12
  ([automation_batch.md](automation_batch.md), mục "Kiểm chứng").
- Chưa xem bằng giao diện public trong lúc đổi bản; mới kiểm bằng script dựng lại môi trường của bản public.

## 4. Trạng thái để lại

- Registry `retail_lab.retail_control.state`:
  - `active` = `b25b3e471bae45768a79e4a2`;
  - 2 bản `ready`: `cfe19211…` của CLI sáng nay và `b25b3e47…` của Airflow;
  - version `5c754d808b02433b8526a1759e203bb4`.
- Airflow vẫn đang chạy (container `airflow-api`, `airflow-scheduler`, `airflow-dag-processor`, UI `127.0.0.1:8080`) để PM xem.
  DAG không có lịch. Muốn tắt: `docker compose -f docker-compose.airflow.yml stop`.
- Git:
  - 7 commit deep link (`22677c0` → `532b240`) chưa push;
  - hai file sửa dở của người khác (`evidence.py`, `test_ai_forecast.py`) vẫn ở trạng thái chưa commit.
- PM cần làm:
  - `! git push origin app/myuyen`, rồi Reboot bản public;
  - hỏi thử hai câu ở mục 1.4 để kiểm nút mở trang trên public.

## 5. Cho người kiểm (Astra)

- **Phần chỉ có trên máy này:** `warehouse/` bị gitignore (run, snapshot, script kiểm); đọc qua git sẽ không thấy.
  `docs/` không bị ignore: lúc ghi mục này các tài liệu chưa commit, PM cho commit tối 2026-10-17 (xem `git log -- docs/`).
- **Code public đang chạy và code đã kiểm:** bản public đang chạy `6335164` cho tới khi PM push và Reboot. Các lần kiểm sau
  đổi bản dùng code `532b240`. `git diff --stat 6335164 532b240` chỉ gồm 7 file: `ai_explain/links.py`, `tests/test_ai_links.py`,
  `ui/common.py`, `views/ai_explain.py`, `views/ps1_do_dung.py`, `views/ps4_don_mon_gia.py`, `views/ps5_nhom.py`. Đường đọc của
  chat (`tools.py`, `guarded.py`, `evidence.py`, `service.py`) và của app (`dwh/`) không đổi. Vì vậy kết quả đọc bản / quyền
  đã kiểm cũng đúng cho code public hiện tại.
- **Về hồi quy và hai file sửa dở:** đây là suy luận, không phải kiểm trực tiếp. pytest nạp mọi module khi thu thập test, lúc
  bắt đầu chạy, trước 20:18, nên lần hồi quy dùng `evidence.py` cũ. Có bằng chứng độc lập:
  - `test_ai_links.py` 26/26 chạy xong khoảng 20:07, trước khi file bị sửa;
  - mọi lần kiểm Databricks (mục 2–3, và trang mở từ link ở dưới) chạy từ bản xuất sạch `532b240`.
- **Trang mở từ link, đọc Databricks** (`warehouse/pipeline/kiem_deeplink_dbx.py`, AppTest, chỉ đọc):
  - môi trường như bản public: secrets, versioned, SP `retail-web-ro`, code `532b240`, bản đang phục vụ `b25b3e47…`;
  - 6/6 ĐẠT: PS5 region / 2019 và acquisition_channel / 2016; PS4 2021; PS1 2013-2022 và 2014; PS5 `?nam=2031` báo và dùng 2019;
  - kiểu dữ liệu năm của Databricks không làm `url_choice` trượt về mặc định.
- **Lệnh kiểm lại nhanh:**
  - `KIEM_CODE_ROOT=<bản xuất 532b240> .venv/Scripts/python.exe warehouse/pipeline/kiem_sau_doi_ban.py b25b3e471bae45768a79e4a2`;
  - `KIEM_CODE_ROOT=<bản xuất 532b240> .venv/Scripts/python.exe warehouse/pipeline/kiem_deeplink_dbx.py`;
  - bản xuất: `git archive 532b240 apps/retail_app scripts retail_dbt deploy | tar -x -C <thư mục>`.
