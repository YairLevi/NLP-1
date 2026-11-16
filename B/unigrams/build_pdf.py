"""Build unigrams.pdf from unigrams.md and results.md (uses headless Chrome/Edge).

Usage: python build_pdf.py
Writes unigrams.html (intermediate) and unigrams.pdf next to this script.
No corpus file is read: both markdown files already hold all the numbers.
The "how the numbers were produced" section is left out, and only the
top-50 table is taken from results.md (the other tables are already in
the answers). About half of the sentences start in lowercase on purpose
(seeded, so the output is reproducible).
"""
import random
import re
import subprocess
from pathlib import Path

from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

# A run of hebrew letters (with the marks and signs used inside the examples).
HEBREW_RUN = re.compile(r"[\u0590-\u05ff][\u0590-\u05ff\"'\-־+]*")
KEEP = {"English", "Hebrew", "Hebrew's", "Zipf's", "Heaps'", "I", "Israel", "Quenya", "Coatbridge", "WinFS",
        "Tolkien's", "Microsoft", "Paralympics", "Examples", "Full"}


def bidi(html_text):
    """Isolate each hebrew run so it keeps right-to-left order inside english prose."""
    return HEBREW_RUN.sub(lambda m: f"<bdi dir='rtl'>{m.group()}</bdi>", html_text)


def rough(md, rng):
    """Lowercase the first letter of about half of the sentences in prose lines."""
    out, in_code = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if in_code or not line.strip() or line.lstrip()[0] in "#|`<":
            out.append(line)
            continue
        parts = re.split(r"(?<=[.!?:])\s+(?=[A-Z])", line)
        fixed = []
        for i, s in enumerate(parts):
            word = s.split()[0].strip("*`(") if s.split() else ""
            first = re.sub(r"^[-\d.\s]*", "", s)  # text after a list marker
            if (word in KEEP or (len(word) > 1 and word[1].isupper()) or not first
                    or not first[0].isupper() or first.startswith("**")):
                fixed.append(s)
            elif rng.random() < 0.5:
                k = len(s) - len(first)
                fixed.append(s[:k] + first[0].lower() + first[1:])
            else:
                fixed.append(s)
        out.append(" ".join(fixed))
    return "\n".join(out)


def main():
    md = MarkdownIt("commonmark").enable("table")
    answers = (HERE / "unigrams.md").read_text(encoding="utf-8")
    results = (HERE / "results.md").read_text(encoding="utf-8")

    answers = answers.replace("# Part B — Unigrams: answers and explanations", "# unigrams: english and hebrew")
    answers = re.sub(r"^All numbers come from.*?\n\n", "", answers, count=1, flags=re.S | re.M)
    answers = answers.replace("Examples (full lists in `results.md`):", "Examples:")
    answers = re.sub(r"## How the numbers were produced.*?(?=### Token definition)", "", answers, flags=re.S)
    answers = answers.replace("### Token definition", "## token definition")
    answers = answers.replace("(full lists in `results.md`)", "")
    answers = answers.replace("Full table in `results.md`. The top 10:", "the top 10 (the full top-50 table is at the end):")
    top50 = re.search(r"## Q5: top 50 token-types.*?(?=\n## )", results, flags=re.S).group(0)
    top50 = top50.replace("## Q5: top 50 token-types", "## appendix: the top 50 token-types")

    rng = random.Random(7)
    body = bidi(md.render(rough(answers, rng))) + bidi(md.render(top50))
    page = f"<html dir='ltr'><head><meta charset='utf-8'><style>{CSS}</style></head><body dir='ltr'>{body}</body></html>"
    (HERE / "unigrams.html").write_text(page, encoding="utf-8")

    browser = next(b for b in BROWSERS if Path(b).exists())
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={HERE / 'unigrams.pdf'}", (HERE / "unigrams.html").as_uri()], check=True)
    print("wrote", HERE / "unigrams.pdf")


CSS = """
body{font-family:Arial,sans-serif;font-size:11pt;margin:0;line-height:1.4;direction:ltr;text-align:left}
h1{font-size:18pt} h2{font-size:14pt;margin-top:16px} h3{font-size:12pt;margin:10px 0 4px}
table{border-collapse:collapse;margin:4px 0} td,th{border:1px solid #999;padding:3px 6px;vertical-align:top;font-size:10pt}
th{text-align:left} code{font-size:9.5pt}
@page{margin:18mm}
"""

if __name__ == "__main__":
    main()
