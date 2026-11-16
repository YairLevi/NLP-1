"""Build ngrams.pdf from out/<lang>.ngrams.json (uses headless Chrome/Edge).

Usage: python build_pdf.py
Writes ngrams.html (intermediate) and ngrams.pdf next to this script.
The discussion text lives in DISCUSSION below; all prose starts lowercase
on purpose (assignment-submission style requested by the author).
"""
import html
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANGS = ("english", "hebrew")
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
MAX_LONG_CHARS = 1800  # the longest n-gram may be a whole paragraph: clip it for display

DISCUSSION = (HERE / "discussion.html").read_text(encoding="utf-8")


def cell(text, lang):
    d = "rtl" if lang == "hebrew" else "ltr"
    return f'<span dir="{d}">{html.escape(text)}</span>'


def top_table(rows, lang):
    out = ["<table><tr><th>#</th><th>n-gram</th><th>freq.</th></tr>"]
    for i, r in enumerate(rows, 1):
        out.append(f"<tr><td>{i}</td><td class='g'>{cell(r['ngram'], lang)}</td><td>{r['count']:,}</td></tr>")
    out.append("</table>")
    return "".join(out)


def main():
    data = {l: json.load(open(HERE / "out" / f"{l}.ngrams.json", encoding="utf-8")) for l in LANGS}
    parts = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>",
             "<h1>n-grams: english and hebrew</h1>",
             "<p>an n-gram is n consecutive tokens (token = maximal run of non-space, non-punctuation "
             "characters, as defined in the assignment; the file is read as one token stream). "
             "all counts below are exact.</p>"]
    parts.append("<h2>corpus and search size</h2><table><tr><th></th><th>english</th><th>hebrew</th></tr>")
    parts.append("<tr><td>tokens</td>" + "".join(f"<td>{data[l]['tokens']:,}</td>" for l in LANGS) + "</tr>")
    parts.append("<tr><td>longest repeated n</td>" + "".join(f"<td>{data[l]['longest']['n']}</td>" for l in LANGS) + "</tr>")
    parts.append("</table>")
    for n in ("5", "10"):
        parts.append(f"<h2>top-10 {n}-grams</h2>")
        for l in LANGS:
            parts.append(f"<h3>{l}</h3>" + top_table(data[l]["top"][n], l))
    parts.append("<h2>longest n-gram with frequency above 1</h2>")
    for l in LANGS:
        lo = data[l]["longest"]
        parts.append(f"<h3>{l}: n = {lo['n']}, {lo['how_many']:,} distinct n-gram(s) of this length</h3>"
                     "<table><tr><th>n-gram (clipped for display)</th><th>freq.</th></tr>")
        for ex in lo["examples"]:
            g = ex["ngram"]
            if len(g) > MAX_LONG_CHARS:
                g = g[:MAX_LONG_CHARS] + " ..."
            parts.append(f"<tr><td class='g'>{cell(g, l)}</td><td>{ex['count']:,}</td></tr>")
        parts.append("</table>")
    parts.append("<h2>repeated n-grams per length n</h2><table><tr><th>n</th>")
    parts.append("".join(f"<th>{l}: distinct</th><th>{l}: positions</th>" for l in LANGS) + "</tr>")
    by = {l: {x["n"]: x for x in data[l]["levels"]} for l in LANGS}
    for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 32):
        parts.append(f"<tr><td>{n}</td>")
        for l in LANGS:
            x = by[l].get(n)
            parts.append(f"<td>{x['grams']:,}</td><td>{x['positions']:,}</td>" if x else "<td>-</td><td>-</td>")
        parts.append("</tr>")
    parts.append("</table>")
    parts.append("<h2>discussion</h2>" + DISCUSSION + "</body></html>")
    (HERE / "ngrams.html").write_text("".join(parts), encoding="utf-8")

    browser = next(b for b in BROWSERS if Path(b).exists())
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={HERE / 'ngrams.pdf'}", (HERE / "ngrams.html").as_uri()], check=True)
    print("wrote", HERE / "ngrams.pdf")


CSS = """
body{font-family:Arial,'David',sans-serif;font-size:11pt;margin:0;line-height:1.4}
h1{font-size:19pt} h2{font-size:14pt;margin-top:18px;border-bottom:1px solid #999}
h3{font-size:11.5pt;margin:10px 0 4px}
table{border-collapse:collapse;margin:4px 0;width:100%} td,th{border:1px solid #bbb;padding:3px 6px;vertical-align:top;font-size:10pt}
th{background:#eee;text-align:left} td.g{word-break:break-word} td:last-child{white-space:nowrap}
@page{margin:18mm}
"""

if __name__ == "__main__":
    main()
