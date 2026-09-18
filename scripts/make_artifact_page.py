#!/usr/bin/env python3
"""Derive the Claude-Artifact variant of docs/index.html: the same page without the document skeleton
(the Artifact viewer wraps the content itself). Output goes to the path given as the first argument.
    python3 scripts/make_artifact_page.py /path/to/artifact_index.html
"""
import re, sys
from pathlib import Path
src = Path(__file__).resolve().parents[1] / "docs/index.html"
html = src.read_text(encoding="utf-8")
html = re.sub(r"<!doctype html>\s*", "", html, flags=re.I)
html = re.sub(r"<html[^>]*>\s*", "", html, flags=re.I); html = re.sub(r"</html>\s*$", "", html, flags=re.I)
html = re.sub(r"<head>\s*", "", html, flags=re.I); html = re.sub(r"\s*</head>", "", html, flags=re.I)
html = re.sub(r"<body>\s*", "", html, flags=re.I); html = re.sub(r"\s*</body>", "", html, flags=re.I)
html = re.sub(r'<meta charset="utf-8">\s*', "", html); html = re.sub(r'<meta name="viewport"[^>]*>\s*', "", html)
out = Path(sys.argv[1]); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(html, encoding="utf-8")
print(f"wrote {out} ({len(html)} chars)")
