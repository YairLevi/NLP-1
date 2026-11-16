"""Build unigrams.pdf from unigrams.md and results.md (uses headless Chrome/Edge).

Usage: python build_pdf.py
Writes unigrams.html (intermediate) and unigrams.pdf next to this script.
No corpus file is read: both markdown files already hold all the numbers.
"""
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


def bidi(html_text):
    """Isolate each hebrew run so it keeps right-to-left order inside english prose."""
    return HEBREW_RUN.sub(lambda m: f"<bdi dir='rtl'>{m.group()}</bdi>", html_text)


def main():
    md = MarkdownIt("commonmark").enable("table")
    answers = (HERE / "unigrams.md").read_text(encoding="utf-8")
    results = (HERE / "results.md").read_text(encoding="utf-8")
    # The answers file links to results.md; in the pdf the tables follow as an appendix.
    answers = answers.replace("# Part B — Unigrams: answers and explanations",
                              "# unigrams: english and hebrew")
    answers = answers.replace("[`results.md`](results.md)", "the appendix (full tables)")
    answers = answers.replace("`results.md`", "the appendix")
    results = results.replace("# Unigram results", "# appendix: full tables")
    results = results.replace("Explanations of the phenomena are in [`unigrams.md`](unigrams.md).",
                              "Explanations are in the answers above.")
    body = bidi(md.render(answers)) + "<div class='pb'></div>" + bidi(md.render(results))
    page = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    (HERE / "unigrams.html").write_text(page, encoding="utf-8")

    browser = next(b for b in BROWSERS if Path(b).exists())
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={HERE / 'unigrams.pdf'}", (HERE / "unigrams.html").as_uri()], check=True)
    print("wrote", HERE / "unigrams.pdf")


CSS = """
body{font-family:Arial,'David',sans-serif;font-size:11pt;margin:0;line-height:1.4}
h1{font-size:19pt} h2{font-size:14pt;margin-top:18px;border-bottom:1px solid #999}
h3{font-size:11.5pt;margin:10px 0 4px}
table{border-collapse:collapse;margin:4px 0} td,th{border:1px solid #bbb;padding:3px 6px;vertical-align:top;font-size:10pt}
th{background:#eee;text-align:left}
code{font-size:9.5pt} pre{background:#f4f4f4;padding:6px;font-size:9.5pt}
.pb{page-break-before:always}
@page{margin:18mm}
"""

if __name__ == "__main__":
    main()
