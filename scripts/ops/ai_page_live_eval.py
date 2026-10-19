"""Live eval khung "AI diễn giải" trên trang PS1–PS5 (B8) với MÔ HÌNH THẬT. Tốn phí API theo token.

PM tự chạy ngoài Claude Code (luật 7, docs/giao_viec_theo_so_do.md §3), từ root, sau khi có `.env.ai.local`:
    $env:PYTHONUTF8=1
    .venv\\Scripts\\python.exe scripts/ops/ai_page_live_eval.py --runs 3
Mặc định đọc bản active local (chế độ versioned, warehouse/pipeline/state.json). `--backend databricks` đọc bản đang phục vụ
trên cloud bằng SP AI. Mỗi trang dùng lựa chọn mặc định của trang (PS1 kỳ phân tích, PS3 tháng cao / thấp, PS4 và PS5 năm 2019).

Kết quả: bảng tóm tắt ra màn hình + JSONL ở warehouse/ai_eval/ (Git ignore): lựa chọn, trạng thái, lời đã kiểm, lời thô,
lỗi kiểm, token, thời gian, bản dữ liệu. Chấm máy chỉ gồm: trạng thái ok, không còn cụm từ cấm. Phần "lời có vượt số không,
stakeholder có hiểu không" vẫn phải đọc tay answer_md. Không ghi khóa API.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('RETAIL_RELEASE_MODE', 'versioned')
os.environ.setdefault('RETAIL_RELEASE_STATE', str(ROOT / 'warehouse' / 'pipeline' / 'state.json'))
sys.path.insert(0, str(ROOT / 'apps' / 'retail_app'))

from ai_explain import page_explain as pe, provider, service, tools   # noqa: E402
from dwh import releases                                                # noqa: E402

OUT = ROOT / 'warehouse' / 'ai_eval'
PRICE_IN, PRICE_OUT = 0.30, 1.20    # như scripts/ops/ai_live_eval.py: deepseek-flash giờ cao điểm, kiểm 2026-10-05, chỉ để ước
# Cụm từ PM đã loại (FB01 / FB02, 2026-10-18) và lỗi đọc tay của các lượt live 2026-10-18. Chấm máy chỉ bắt chữ, không thay đọc tay.
BANNED = ['thực nhận', 'hụt', 'thất thoát', 'lãng phí', 'ngẫu nhiên', 'ý nghĩa thống kê', 'chắc chắn', 'luôn luôn']
RANKING = re.compile(r'chủ yếu|phần lớn|đa số|nhiều nhất|lớn nhất|đứng đầu')


def requests() -> list[pe.PageRequest]:
    return [pe.request_ps1(tools.ANALYSIS_WINDOW, 'total'), pe.request_ps2(), pe.request_ps3('mua_vu'),
            pe.request_ps4('2019', 'year', 2018, 2019, 'Năm 2019 so với 2018'), pe.request_ps5('category', 2019)]


def release_meta(backend: str, turn) -> dict | None:
    """Bản dữ liệu mà lượt này đọc: lấy từ bằng chứng của tool (data_version), giống ai_live_eval._release_meta."""
    for res in turn.results.values():
        dv = res.evidence.data_version if res.evidence is not None else {}
        if dv.get('release_id'):
            return {k: dv.get(k) for k in ('release_id', 'snapshot_id', 'run_id')}
    if backend == 'duckdb' and releases.enabled(backend):
        r = releases.choose(releases.local_state())
        return {k: r[k] for k in ('release_id', 'snapshot_id', 'run_id')}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--pages', nargs='*', choices=list(pe.PAGES), help='mặc định cả năm trang')
    ap.add_argument('--backend', default='duckdb', choices=('duckdb', 'databricks'))
    a = ap.parse_args()
    p = provider.from_config()
    if p is None:
        print('Chưa có RETAIL_AI_API_KEY (biến môi trường hoặc .env.ai.local). Không chạy.')
        return 2
    reqs = [r for r in requests() if not a.pages or r.page in a.pages]
    print(f'prompt trang {pe.PAGE_PROMPT_VERSION} · prompt chat {service.PROMPT_VERSION} · tool {tools.TOOL_VERSION} '
          f'· backend {a.backend} · {len(reqs)} trang × {a.runs} lượt')
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    log = OUT / f'page_{stamp}_{a.backend}_{os.getpid()}.jsonl'
    rows, tin, tout = [], 0, 0
    with log.open('w', encoding='utf-8') as f:
        for run in range(1, a.runs + 1):
            for req in reqs:
                t0 = time.monotonic()
                t = pe.explain(req, a.backend, p)
                text = (t.answer_md or '').lower()
                banned = [w for w in BANNED if w in text]
                ranking = sorted(set(RANKING.findall(text)))
                tin, tout = tin + t.prompt_tokens, tout + t.completion_tokens
                rec = {'run': run, 'page': req.page, 'label': req.label, 'question': req.question,
                       'status': t.status, 'auto_pass': t.status == 'ok' and not banned, 'banned_hits': banned,
                       'ranking_words': ranking, 'answer_md': t.answer_md, 'message': t.message,
                       'claims': {k: {'path': pth, 'value': str(v), 'shown': s} for k, (pth, v, s) in t.values.items()},
                       'validation_errors': t.validation_errors, 'repair_errors': t.repair_errors,
                       'raw_final': t.raw_final, 'raw_first': t.raw_first, 'llm_calls': t.llm_calls,
                       'prompt_tokens': t.prompt_tokens, 'completion_tokens': t.completion_tokens,
                       'seconds': round(time.monotonic() - t0, 1), 'model': t.model, 'page_prompt_version': t.prompt_version,
                       'release': release_meta(a.backend, t)}
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                f.flush()
                rows.append(rec)
                flag = 'ĐẠT' if rec['auto_pass'] else 'TRƯỢT'
                print(f"[{run}] {req.page} {flag:5} {t.status:24} sửa {max(t.llm_calls - 1, 0)} lần"
                      + (f" · cụm cấm {banned}" if banned else '') + (f" · từ xếp hạng {ranking}" if ranking else ''))
    ok = sum(r['auto_pass'] for r in rows)
    rel = next((r['release'] for r in rows if r['release']), None)
    print(f'\nChấm máy: {ok}/{len(rows)} đạt (trạng thái ok, không cụm cấm). Bản dữ liệu: {rel}')
    print(f'Token vào {tin:,} · ra {tout:,} · ước {tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT:.2f} USD (giá niêm yết)')
    print(f'Log: {log.relative_to(ROOT)}  ← gửi đường dẫn này cho Claude để đọc tay answer_md')
    return 0


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    sys.exit(main())
