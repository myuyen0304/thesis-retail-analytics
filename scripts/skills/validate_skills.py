"""Kiểm cấu trúc, link và đồng bộ skill; không đánh giá hành vi LLM."""
import argparse
from pathlib import Path
import re
import sys
from urllib.parse import unquote

import yaml

from sync_skills import SKILLS, SyncError, collect, sync


def validate(root: Path) -> list[str]:
    errors = []
    for location in ('.agents/skills', '.claude/skills'):
        base = root / location
        try:
            files = collect(base, required=True)
        except (SyncError, OSError, UnicodeError) as exc:
            errors.append(str(exc))
            continue
        for name in SKILLS:
            text = files[f'{name}/SKILL.md'].decode('utf-8')
            match = re.match(r'\A---\n(.*?)\n---\n', text, re.DOTALL)
            if not match:
                errors.append(f'{location}/{name}: thiếu frontmatter')
                continue
            try:
                data = yaml.safe_load(match.group(1))
            except yaml.YAMLError as exc:
                errors.append(f'{name}: {exc}')
                continue
            if not isinstance(data, dict) or data.get('name') != name:
                errors.append(f'{location}/{name}: name không khớp thư mục')
            description = data.get('description') if isinstance(data, dict) else None
            if not isinstance(description, str) or not description.strip() or len(description) > 1024:
                errors.append(f'{location}/{name}: description không hợp lệ')
            if re.search(r'\[TODO:|\bTBD\b', text):
                errors.append(f'{location}/{name}: còn placeholder')
        for key, content in files.items():
            if not key.endswith('.md'):
                continue
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', content.decode('utf-8')):
                if '://' in link or link.startswith('#'):
                    continue
                target = unquote(link.split('#', 1)[0])
                if not (base / key).parent.joinpath(target).exists():
                    errors.append(f'{location}/{key}: link thiếu {target}')
    try:
        errors.extend(sync(root))
    except (SyncError, OSError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('PASS: 6 source + 6 bản Claude, frontmatter, link nội bộ và sync.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
