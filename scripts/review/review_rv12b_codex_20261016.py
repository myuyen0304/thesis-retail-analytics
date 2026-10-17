"""Kiểm độc lập RV12 lượt 2: lời phủ định không được che một phép gán kỳ sai."""

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


CASES = [
    (
        "control_reference",
        "Chưa có dự báo năm 2025. Riêng tháng 8/2023, dự báo G là {c1}.",
        True,
    ),
    (
        "contradiction_next_sentence",
        "Chưa có dự báo năm 2025. Riêng tháng 8/2023, dự báo G là {c1}. "
        "Năm 2025 chưa có dự báo nhưng số này là dự báo năm 2025.",
        False,
    ),
    (
        "contradiction_same_sentence",
        "Riêng tháng 8/2023, dự báo G là {c1}. "
        "Năm 2025 chưa có dự báo nhưng có thể dùng số này làm dự báo năm 2025.",
        False,
    ),
]


def main() -> int:
    releases.reset()
    rows = []
    for name, answer, expected in CASES:
        reply = final("no_data", answer, [{"id": "c1", "path": "T1.rows[0].g_forecast"}])
        turn = service.run_turn(
            "Dự báo doanh thu năm 2025?",
            [],
            "duckdb",
            FakeProvider(call("get_forecast", metric="G", period="month", year=2023, month=8), reply, reply),
        )
        shown = turn.status == "no_data" and bool(turn.answer_md)
        rows.append(
            {
                "case": name,
                "expected_shown": expected,
                "actual_shown": shown,
                "status": turn.status,
                "validation_errors": turn.validation_errors,
                "passed": shown == expected,
            }
        )
    output = ROOT / "warehouse" / "reviews" / "ai_gd2_20261015" / "codex_rv12b_extra.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in rows:
        print(f"{row['case']}: expected_shown={row['expected_shown']}, "
              f"actual_shown={row['actual_shown']}, status={row['status']}, passed={row['passed']}")
    return int(not all(row["passed"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
