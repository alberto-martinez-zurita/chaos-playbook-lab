"""Build paper.pdf from the per-section .md files in paper/.

Pipeline:
  1. Concatenate the section .md files in order, with a YAML title block.
  2. Run pandoc to produce a single self-contained HTML (figures embedded
     as base64, CSS embedded, Markdown tables converted to HTML).
  3. Run Chrome headless to print that HTML to PDF.

Outputs:
  paper/paper.combined.md   — the concatenated markdown (debug)
  paper/paper.html          — self-contained HTML (debug)
  paper/paper.pdf           — final PDF
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
SECTIONS = [
    "00-abstract.md",
    "01-introduction.md",
    "02-related-work.md",
    "03-methodology.md",
    "04-results.md",
    "05-discussion.md",
    "06-conclusions.md",
    "07-references.md",
]

TITLE_BLOCK = """---
abstract-title: ""
---
"""

CSS = """
@page {
  size: A4;
  margin: 22mm 18mm 22mm 18mm;
  @bottom-center { content: counter(page); font-size: 9pt; color: #555; }
}

html, body {
  font-family: "Charter", "Georgia", "Times New Roman", serif;
  font-size: 10.5pt;
  line-height: 1.45;
  color: #111;
  max-width: 100%;
}

h1, h2, h3, h4 {
  font-family: "Helvetica Neue", "Inter", "Segoe UI", Arial, sans-serif;
  color: #111;
  page-break-after: avoid;
}

/* Title page — CoT-style academic header */
h1:first-of-type {
  font-size: 19pt;
  line-height: 1.25;
  margin: 0.4em 0 0.4em 0;
  text-align: center;
  font-weight: 700;
  letter-spacing: -0.005em;
  border: none;
  padding: 0;
}

p.subtitle {
  text-align: center;
  font-size: 10.5pt;
  font-style: italic;
  color: #555;
  margin: 0.2em 0 1.4em 0;
}

p.author {
  text-align: center;
  font-size: 11.5pt;
  color: #111;
  margin: 0.4em 0 0.2em 0;
  font-family: "Helvetica Neue", "Inter", "Segoe UI", Arial, sans-serif;
}

p.date {
  text-align: center;
  font-size: 9.5pt;
  color: #666;
  margin: 0.2em 0 0.6em 0;
}

/* Horizontal rule after title block — the "bar" academic papers use */
hr {
  border: none;
  border-top: 0.6pt solid #888;
  margin: 0.4em 18% 1.4em 18%;
}

/* "Abstract" heading — bold centered, CoT-style, with breathing room above */
h1:nth-of-type(2) {
  font-size: 11pt;
  text-align: center;
  font-weight: 700;
  margin: 2.2em 0 0.8em 0;
  border: none;
  text-transform: none;
  letter-spacing: 0.04em;
}

/* Abstract paragraphs — all of them get the indent + smaller font */
h1:nth-of-type(2) ~ p {
  font-size: 10pt;
  margin: 0 8% 0.8em 8%;
  text-align: justify;
}

/* Reset paragraphs after Introduction (h1 #3 onward) back to body styling */
h1:nth-of-type(2) ~ h1 ~ p {
  font-size: 10.5pt;
  margin: 0 0 0.8em 0;
}

h1 { font-size: 14.5pt; margin-top: 2.4em; border-bottom: 0.4pt solid #d8dade; padding-bottom: 0.25em; }
h2 { font-size: 12.5pt; margin-top: 1em; }
h3 { font-size: 11pt;   margin-top: 0.8em; }

p { text-align: justify; hyphens: auto; }

code, pre {
  font-family: "JetBrains Mono", "Consolas", "Menlo", monospace;
  font-size: 9.5pt;
}
pre {
  background: #f6f7f8;
  border: 1px solid #e3e6ea;
  border-radius: 3px;
  padding: 8px 10px;
  overflow-x: auto;
  white-space: pre-wrap;
}
code { background: #f1f3f4; padding: 0 2px; border-radius: 2px; }
pre code { background: transparent; padding: 0; }

table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5em 0 1em 0;
  font-size: 9.5pt;
}
th, td {
  border-top: 1px solid #ccc;
  border-bottom: 1px solid #ccc;
  padding: 4px 8px;
  vertical-align: top;
  word-break: normal;
  overflow-wrap: anywhere;
}
td code, th code { word-break: break-word; }

/* Runtime/identifier table — smaller font, wider Runtime + Reasoning cols */
.table-runtime table { font-size: 8.5pt; }
.table-runtime table th:nth-child(3),
.table-runtime table td:nth-child(3),
.table-runtime table th:nth-child(6),
.table-runtime table td:nth-child(6) { white-space: nowrap; }

/* Excluded-models table — short cols 1-3 must not break; let Reason col 4 take the width */
.table-excluded table th:nth-child(1),
.table-excluded table td:nth-child(1),
.table-excluded table th:nth-child(2),
.table-excluded table td:nth-child(2),
.table-excluded table th:nth-child(3),
.table-excluded table td:nth-child(3) { white-space: nowrap; }
th { background: #f4f6f8; text-align: left; font-weight: 600; }

figure { margin: 0.6em 0 1em 0; text-align: center; }
img { max-width: 100%; height: auto; }
figcaption { font-size: 9.5pt; color: #555; margin-top: 0.3em; }

blockquote {
  border-left: 3px solid #d0d7de;
  margin: 0.6em 0;
  padding: 0.2em 0.8em;
  color: #444;
  background: #fafbfc;
}

a { color: #1f6feb; text-decoration: none; }

/* Section dividers */
h1 + p, h2 + p { margin-top: 0.4em; }
hr {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 1em 0;
}
"""


def find_chrome() -> str:
    candidates = [
        os.environ.get("CHROME"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    raise RuntimeError("Could not locate Chrome or Edge. Set CHROME=<path> in env.")


def main() -> int:
    if shutil.which("pandoc") is None:
        print("ERROR: pandoc not in PATH", file=sys.stderr)
        return 2

    chrome = find_chrome()
    print(f"Using browser: {chrome}")

    import re
    INCLUDE_RE = re.compile(r"<!--\s*include:\s*([^\s>]+)\s*-->")

    def resolve_includes(text: str) -> str:
        def repl(match: re.Match) -> str:
            inc_path = (PAPER / match.group(1)).resolve()
            if not inc_path.exists():
                print(f"WARN: include not found: {inc_path}", file=sys.stderr)
                return match.group(0)
            return inc_path.read_text(encoding="utf-8")
        # Resolve nested includes by repeating until fixed point.
        prev = None
        while text != prev:
            prev = text
            text = INCLUDE_RE.sub(repl, text)
        return text

    parts: list[str] = [TITLE_BLOCK]
    for sec in SECTIONS:
        p = PAPER / sec
        if not p.exists():
            print(f"WARN: missing {p}", file=sys.stderr)
            continue
        body = resolve_includes(p.read_text(encoding="utf-8"))
        parts.append("\n\n")
        parts.append(body)
    combined_md = "".join(parts)
    combined_path = PAPER / "paper.combined.md"
    combined_path.write_text(combined_md, encoding="utf-8")
    print(f"Wrote {combined_path}")

    css_path = PAPER / "paper.css"
    css_path.write_text(CSS, encoding="utf-8")

    html_path = PAPER / "paper.html"
    cmd = [
        "pandoc",
        str(combined_path),
        "-f", "gfm+yaml_metadata_block+fenced_divs",
        "-t", "html5",
        "--standalone",
        "--embed-resources",
        "--css", str(css_path),
        "-o", str(html_path),
        f"--resource-path={PAPER}",
    ]
    print("Running pandoc:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=PAPER)
    print(f"Wrote {html_path}")

    pdf_path = PAPER / "paper.pdf"
    file_url = "file:///" + str(html_path).replace("\\", "/").lstrip("/")
    cmd2 = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        file_url,
    ]
    print("Running browser:", " ".join(cmd2))
    subprocess.run(cmd2, check=True)
    print(f"Wrote {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
