"""Kiểm độc lập RV12 lượt 3: câu hỏi gán số sai kỳ, phủ định lệch nghĩa và tham khảo đúng."""

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "retail_app"))
os.environ["RETAIL_RELEASE_MODE"] = "versioned"
os.environ["RETAIL_RELEASE_STATE"] = str(ROOT / "warehouse" / "pipeline" / "state.json")

from ai_explain import service  # noqa: E402
from dwh import releases  # noqa: E402
from tests.test_ai_chat import FakeProvider, call, final  # noqa: E402


REFERENCE = "Riêng tháng 8/2023, dự báo G là {c1}. "
CASES = [
    ("control_reference", "no_data", "Chưa có dự báo năm 2025. " + REFERENCE, True),
    ("control_clarifying_question", "needs_clarification",
     "Chưa có dự báo năm 2025. " + REFERENCE + "Bạn muốn xem kỳ nào khác?", True),
    ("wrong_year_rhetorical_question", "no_data",
     REFERENCE + "Năm 2025 chưa có dự báo nhưng số này là dự báo năm 2025?", False),
    ("wrong_year_offer", "needs_clarification",
     REFERENCE + "Năm 2025 chưa có dự báo. Bạn có muốn dùng số này làm dự báo năm 2025?", False),
    ("wrong_year_unadjusted", "no_data",
     REFERENCE + "Số này là dự báo năm 2025 chưa điều chỉnh.", False),
    ("wrong_year_double_negative", "no_data",
     REFERENCE + "Không có lý do gì để không coi đây là dự báo năm 2025.", False),
    ("wrong_year_missing_reason", "no_data",
     REFERENCE + "Chưa có lý do gì để không coi đây là dự báo năm 2025.", False),
    ("wrong_year_unadjustable", "no_data",
     REFERENCE + "Số này là dự báo năm 2025 chưa thể điều chỉnh.", False),
    ("wrong_year_implicit_double_negative", "no_data",
     "Năm 2025 chưa có dự báo. " + REFERENCE + "Không có lý do gì để không dùng số này.", False),
    ("reference_as_benchmark", "no_data",
     "Năm 2025 chưa có dự báo. " + REFERENCE + "Có thể dùng số này làm mốc tham khảo.", True),
    ("reference_as_comparison_only", "no_data",
     "Năm 2025 chưa có dự báo. " + REFERENCE
     + "Có thể dùng số này làm mốc tham khảo để so sánh, không phải dự báo năm 2025.", True),
]


def main() -> int:
    releases.reset()
    rows = []
    for name, status, answer, expected in CASES:
        reply = final(status, answer, [{"id": "c1", "path": "T1.rows[0].g_forecast"}])
        turn = service.run_turn(
            "Dự báo doanh thu năm 2025?",
            [],
            "duckdb",
            FakeProvider(call("get_forecast", metric="G", period="month", year=2023, month=8), reply, reply),
        )
        shown = turn.status == status and bool(turn.answer_md)
        passed = shown if expected else turn.status == "answer_validation_failed" and not turn.answer_md
        rows.append({
            "case": name,
            "expected_shown": expected,
            "actual_shown": shown,
            "status": turn.status,
            "validation_errors": turn.validation_errors,
            "passed": passed,
        })
    output = ROOT / "warehouse" / "reviews" / "ai_gd2_20261015" / "codex_rv12c_extra.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in rows:
        print(f"{row['case']}: expected_shown={row['expected_shown']}, "
              f"actual_shown={row['actual_shown']}, status={row['status']}, passed={row['passed']}")
    return int(not all(row["passed"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
