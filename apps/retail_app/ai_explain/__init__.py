"""AI Explain cho chat PS1–PS5 (docs/ai_explain_plan.md). Mốc AI0–AI1: hợp đồng + công cụ query, CHƯA có LLM.

- contracts.py      : trạng thái, kết quả tool, bằng chứng
- metric_catalog.py : định nghĩa metric có version, ma trận khả năng (mở / chưa mở)
- tools.py          : tool registry, kiểm tham số chặt, adapter đọc bảng reporting đã kiểm chứng

Query engine tính số; LLM (từ AI2) chỉ chọn tool và diễn giải kết quả có bằng chứng.
"""
