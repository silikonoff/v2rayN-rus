#!/usr/bin/env python3
"""Check UTF-8 and local Markdown links in the Russian documentation."""

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "README.md", *sorted((ROOT / "docs" / "ru").glob("*.md"))]
LINK = re.compile(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)")


def anchors(content: str) -> set[str]:
    """Approximate GitHub heading IDs, including duplicate heading suffixes."""
    counts: dict[str, int] = {}
    result = set()
    for line in content.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        title = match.group(1).lower()
        slug = "".join(c for c in title if c.isalnum() or c in " _-")
        slug = slug.replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def main() -> int:
    errors = []
    for path in FILES:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"{path.relative_to(ROOT)}: {error}")
            continue
        if "\ufffd" in content:
            errors.append(f"{path.relative_to(ROOT)}: replacement character")
        for target in LINK.findall(content):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            dest = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not dest.exists():
                errors.append(f"{path.relative_to(ROOT)}: missing {target}")
            elif parsed.fragment and dest.is_file() and dest.suffix.lower() == ".md":
                if unquote(parsed.fragment) not in anchors(dest.read_text(encoding="utf-8")):
                    errors.append(f"{path.relative_to(ROOT)}: missing anchor {target}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"UTF-8, local link targets and heading anchors checked: {len(FILES)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
