"""Adapter LLM cho AI Explain (docs/ai_explain_plan.md §3, mốc AI2). Một client chuẩn OpenAI Chat Completions:
DeepSeek (dev, PM chốt 2026-10-04) và OpenAI (sau này) đổi bằng cấu hình, không sửa code.

Cấu hình: biến môi trường, hoặc file cá nhân `.env.ai.local` ở root (Git ignore). Biến môi trường được ưu tiên.
    RETAIL_AI_API_KEY    khóa API (KHÔNG commit, không dán vào chat)
    RETAIL_AI_BASE_URL   mặc định https://api.deepseek.com
    RETAIL_AI_MODEL      mặc định deepseek-flash
Model/giá kiểm trên api-docs.deepseek.com ngày 2026-10-05: deepseek-flash có gọi tool; DeepSeek bật "thinking" mặc định,
khi bật phải gửi lại reasoning_content ở mọi lượt sau. Adapter này LUÔN tắt thinking với DeepSeek (không cấu hình được):
nhanh, rẻ, và lịch sử tin nhắn không cần mang reasoning_content. Muốn bật thì phải sửa Reply.message để giữ trường đó.

Model chỉ nhận: câu hỏi, ngữ cảnh có cấu trúc, schema tool, kết quả TỔNG HỢP của tool. Không nhận credentials DB,
không nhận dòng cấp khách hàng (tool chỉ đọc bảng reporting).
"""
import json
import os
import time
from dataclasses import dataclass, field

from dwh.connection import ROOT

AI_CONFIG = ROOT / '.env.ai.local'
DEFAULT_BASE_URL = 'https://api.deepseek.com'
DEFAULT_MODEL = 'deepseek-flash'
REQUEST_TIMEOUT_S = 60.0


class ProviderError(Exception):
    """Gọi LLM thất bại (mạng, khóa sai, hết hạn mức của nhà cung cấp...). Không có câu trả lời thay thế."""


def ai_config() -> dict:
    cfg = {}
    if AI_CONFIG.exists():
        for line in AI_CONFIG.read_text(encoding='utf-8').splitlines():
            k, sep, v = line.strip().partition('=')
            if sep and not k.startswith('#'):
                cfg[k.strip()] = v.strip().strip("'\"")
    keys = set(cfg) | {k for k in os.environ if k.startswith('RETAIL_AI_')}
    out = {k: os.environ.get(k) or cfg.get(k) for k in keys}
    return {k: v for k, v in out.items() if v}


@dataclass(frozen=True)
class ToolCallReq:
    id: str
    name: str
    arguments_json: str      # chuỗi JSON thô do model sinh; tools.run kiểm lại toàn bộ


@dataclass
class Reply:
    content: str | None
    tool_calls: list[ToolCallReq]
    message: dict                       # tin nhắn assistant để gửi lại ở lượt sau
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0


@dataclass
class OpenAICompatProvider:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    _client: object = field(default=None, repr=False)

    @property
    def label(self) -> str:
        return f'{self.model} @ {self.base_url}'

    def complete(self, messages: list[dict], tools: list[dict]) -> Reply:
        import openai
        if self._client is None:
            self._client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=REQUEST_TIMEOUT_S,
                                         max_retries=1)
        extra = {'thinking': {'type': 'disabled'}} if 'deepseek' in self.base_url else None
        t0 = time.monotonic()
        try:
            r = self._client.chat.completions.create(model=self.model, messages=messages, tools=tools or None,
                                                     temperature=0, extra_body=extra)
        except openai.OpenAIError as e:
            raise ProviderError(f'{type(e).__name__}: {str(e)[:200]}') from e
        msg = r.choices[0].message
        calls = [ToolCallReq(c.id, c.function.name, c.function.arguments or '{}') for c in (msg.tool_calls or [])]
        out = {'role': 'assistant', 'content': msg.content or ''}
        if calls:
            out['tool_calls'] = [{'id': c.id, 'type': 'function',
                                  'function': {'name': c.name, 'arguments': c.arguments_json}} for c in calls]
        u = r.usage
        return Reply(msg.content, calls, out, getattr(u, 'prompt_tokens', 0) or 0,
                     getattr(u, 'completion_tokens', 0) or 0, time.monotonic() - t0)


def from_config() -> OpenAICompatProvider | None:
    """Provider theo cấu hình; None nếu chưa có khóa API (trang chat báo cách cấu hình, không lỗi)."""
    c = ai_config()
    if not c.get('RETAIL_AI_API_KEY'):
        return None
    return OpenAICompatProvider(api_key=c['RETAIL_AI_API_KEY'], base_url=c.get('RETAIL_AI_BASE_URL', DEFAULT_BASE_URL),
                                model=c.get('RETAIL_AI_MODEL', DEFAULT_MODEL))


def openai_tools(schemas: list[dict]) -> list[dict]:
    """tools.tool_schemas() (dạng name/description/input_schema) → định dạng function calling của OpenAI/DeepSeek."""
    return [{'type': 'function', 'function': {'name': s['name'], 'description': s['description'],
                                              'parameters': s['input_schema']}} for s in schemas]


def parse_arguments(arguments_json: str):
    """JSON tham số của model → dict; hỏng thì trả chuỗi gốc để tools.run từ chối (không đoán)."""
    try:
        return json.loads(arguments_json)
    except (json.JSONDecodeError, TypeError):
        return arguments_json
