"""Hợp đồng request / result / evidence của một lần gọi tool (docs/ai_explain_plan.md §5, §11.2).

Số tiền giữ `Decimal` chưa làm tròn; tỷ lệ/phân rã là float (DOUBLE của kho). Làm tròn chỉ ở lớp hiển thị.
"""
from dataclasses import dataclass, field
from typing import Any, Literal

# §11.2. `answer_validation_failed` thuộc lớp kiểm câu trả lời của LLM (AI2), tool không trả trạng thái này.
Status = Literal['ok', 'needs_clarification', 'unsupported', 'no_data', 'quality_blocked', 'query_error',
                 'answer_validation_failed']
TOOL_STATUSES = ('ok', 'needs_clarification', 'unsupported', 'no_data', 'quality_blocked', 'query_error')


@dataclass(frozen=True)
class ToolCall:
    """Lời gọi tool do LLM đề xuất (hoặc test). Chưa đáng tin: tools.run kiểm toàn bộ trước khi đọc DB."""
    tool: str
    arguments: dict


@dataclass
class QueryRecord:
    source: str            # bảng/view reporting đã đọc
    sql: str               # câu thực thi (có chỗ đặt tham số), không phải query ID của database
    params: tuple


@dataclass
class Evidence:
    request_id: str                    # do app sinh (uuid4), KHÔNG phải ID truy vấn của database
    tool: str
    tool_version: str
    arguments_applied: dict            # tham số sau chuẩn hóa = đúng thứ đã dùng để lọc
    filters_applied: dict              # điều kiện WHERE thực tế, gồm cả điều kiện cố định của tool
    grain: str
    metrics: list[dict]                # định nghĩa metric dùng trong kết quả (catalog, có decision_status)
    method: str | None                 # phương pháp phân rã/xếp hạng nếu có
    backend: str
    source_description: str            # nơi đọc (connection.describe)
    data_version: dict                 # build marker + phạm vi ngày đặt hàng (rpt_build_info)
    quality: dict                      # rpt_health_summary đọc trong cùng phiên
    definition_version: str            # hash SQL trong checkout: KHÔNG chứng minh DB được build từ đúng bản này
    read_at_utc: str
    queries: list[QueryRecord] = field(default_factory=list)


@dataclass
class ToolResult:
    status: str
    message: str                                   # tiếng Việt, để hiện cho người dùng / đưa LLM diễn giải
    evidence: Evidence | None = None
    rows: list[dict] = field(default_factory=list)  # kết quả tổng hợp, giá trị chưa làm tròn
    derived: dict = field(default_factory=dict)     # chọn/xếp hạng tính từ ĐỦ tập rows (vd. nhóm giảm mạnh nhất)
    missing: list[str] = field(default_factory=list)   # needs_clarification: trường còn thiếu
    rejected: dict = field(default_factory=dict)       # unsupported: trường/giá trị bị từ chối → lý do

    def __post_init__(self):
        assert self.status in TOOL_STATUSES, self.status
        if self.status != 'ok':
            assert not self.rows and not self.derived, 'trạng thái lỗi không được kèm số'

    @property
    def ok(self) -> bool:
        return self.status == 'ok'


Row = dict[str, Any]
