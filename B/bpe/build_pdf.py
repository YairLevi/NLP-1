"""Build bpe.pdf from out/<lang>.analysis.json (uses headless Chrome/Edge).

Usage: python build_pdf.py
Writes bpe.html (intermediate) and bpe.pdf next to this script.
Prose starts lowercase on purpose (same submission style as ngrams.pdf).
"""
import html
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANGS = ("english", "hebrew")
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

# One short explanation per probe word: why the split is (not) sensible.
NOTES = {
    "english": {
        "unfair": "<b>un-</b> negation prefix + stem",
        "untie": "<b>un-</b> reversal prefix + stem",
        "reheat": "<b>re-</b> 'again' + stem",
        "kindness": "<b>-ness§</b> noun-forming suffix",
        "printer": "<b>-er§</b> agent suffix ('one who prints')",
        "smoothed": "<b>-ed§</b> past tense",
        "colouration": "<b>-ation§</b> noun-forming suffix",
        "nonmetal": "<b>non-</b> negation prefix",
        "micrometres": "<b>micro-</b> + plural noun",
        "helpful": "<b>-ful§</b> adjective suffix",
        "photographers": "<b>-ers§</b> agent + plural",
        "Concluding": "<b>-ing§</b> progressive / gerund",
        "underdog": "compound, both parts are words",
        "mountaintop": "compound, both parts are words",
        "crossbow": "compound, both parts are words",
        "rethinking": "re+think+ing, but greedy takes the longer prefix 'ret'; then 'hin' and the word 'king§'",
        "preheat": "pre+heat, but greedy takes 'preh' (frequent in 'prehistoric'), leaving the word 'eat§'",
        "icebergs": "ice+berg+s, split as ic|eber|gs",
        "leggings": "legging+s, split as leg|gin|gs",
        "slippery": "slipper(y) looks like slip+per+y",
        "isomers": "isomer+s, split as is|omer|s",
        "juices": "juice+s, split as ju|ices ('ices' is the plural of 'ice')",
        "cohesive": "co+hes+ive cuts the stem 'cohes-'",
        "vegetables": "vegetable+s, split as veget|ables",
        "realign": "re+align, greedy takes the word 'real'",
        "uncomfortable": "un+comfort+able, split as unc|om|fort|able",
        "betrothed": "betroth+ed, split as betr|oth|ed",
        "Behring": "a name, but split as if it ended in -ing",
        "shower": "<b>-er§</b> is not an agent here: a shower is not 'one who shows'",
        "mister": "<b>-er§</b> again: 'mister' is not mist+er",
        "cipher": "<b>-er§</b> is just the last two letters",
        "shrinking": "shrink+ing, but greedy leaves <b>king§</b>",
        "unify": "<b>uni-</b> 'one' is sensible, <b>fy§</b> (-ify) is cut wrong; and 'un' is not a prefix here",
    },
    "hebrew": {
        "כשהמלכה": "<b>כש</b> 'when' + המלכה",
        "ובחנות": "<b>וב</b> 'and in' + חנות",
        "כשחנות": "<b>כש</b> 'when' + חנות",
        "ולבנים": "<b>ול</b> 'and to' + בנים",
        "ולראות": "<b>ול</b> 'and to' + infinitive ראות",
        "שבתות": "<b>ות§</b> feminine plural suffix",
        "ביתית": "<b>ית§</b> adjective suffix ('home-' adj.)",
        "פסיכולוגית": "<b>ת§</b> feminine adjective ending",
        "שהתמודדו": "<b>שהת</b> = ש 'that' + הת (hitpa'el verb prefix)",
        "התכתבויות": "<b>הת</b> hitpa'el prefix, then root כ-ת-ב",
        "והספרים": "ו+ה+ספרים, split as והס|פרים: the root ס-פ-ר is cut",
        "ובספרייה": "ו+ב+ספרייה, split as ובס|פריי|ה",
        "שבמדינות": "ש+ב+מדינות, split as שבמ|דינ|ות",
        "מהממשלות": "מ+ה+ממשלות, split as מהמ|משלו|ת",
        "כתבתם": "כתב+תם, split as כת|בתם: the root כ-ת-ב is cut",
        "הכתובות": "ה+כתובות, split as הכת|ובות",
        "והמשוררת": "ו+ה+משוררת, split as והמש|ור|רת",
        "מירושלים": "מ+ירושלים, split as מירו|שלים",
        "לחנות": "ל+חנות, split as לח|נות",
        "ולחם": "ו+לחם, split as ולח|ם",
        "תלמידה": "תלמיד+ה, split as תלמי|דה",
        "ושבתות": "ו+שבתות, split as ושב|תות (compare שבת|ות without the ו)",
        "ולשתות": "ו+ל+שתות, split as ולש|תות",
        "ולמות": "<b>ול</b> + <b>מות§</b> 'and to die': both pieces are morphemes",
        "וכמות": "same shape <b>וכ</b> + <b>מות§</b>, but כמות 'quantity' is one stem: כ is not the prefix 'as'",
        "וכשהתלמידים": "ו+כש+ה+תלמידים: <b>שהת</b> now glues the article to the root letter ת",
        "מהממשלות": "<b>ת§</b> is half of the plural ות, not a feminine ending",
    },
}

LABELS = {"sensible": "make sense", "not sensible": "do not make sense",
          "both": "make sense in some words but not in others"}

# A run of hebrew letters, with the § | + - ' signs used inside the examples.
HEBREW_RUN = re.compile(r"[֐-׿][֐-׿§|+\-']*")


def bidi(text):
    """Isolate each hebrew run, so it keeps right-to-left order inside english prose."""
    return HEBREW_RUN.sub(lambda m: f"<bdi dir='rtl'>{m.group()}</bdi>", text)


def pieces(split, lang):
    d = "rtl" if lang == "hebrew" else "ltr"
    inner = "".join(f"<span class='p'>{html.escape(p)}</span>" for p in split)
    return f"<span dir='{d}' class='split'>{inner}</span>"


def probe_table(report, lang, group):
    rows = ["<table><tr><th>word</th><th>greedy BPE split</th><th>why</th></tr>"]
    for word, split in report["probes"][group].items():
        d = "rtl" if lang == "hebrew" else "ltr"
        rows.append(f"<tr><td><span dir='{d}'>{html.escape(word)}</span></td><td>{pieces(split, lang)}</td>"
                    f"<td>{bidi(NOTES[lang].get(word, ''))}</td></tr>")
    rows.append("</table>")
    return "".join(rows)


def item_list(items, lang):
    d = "rtl" if lang == "hebrew" else "ltr"
    return f"<span dir='{d}'>" + " ".join(f"<span class='p'>{html.escape(s)}</span>" for s in items) + "</span>"


def main():
    r = {l: json.load(open(HERE / "out" / f"{l}.analysis.json", encoding="utf-8")) for l in LANGS}
    row = lambda name, f: f"<tr><td>{name}</td>" + "".join(f"<td>{f(r[l])}</td>" for l in LANGS) + "</tr>"
    p = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>",
         "<h1>subword tokenization with bpe</h1>",
         INTRO,
         "<h2>the learned vocabularies (N = 30,000)</h2>",
         "<table><tr><th></th><th>english</th><th>hebrew</th></tr>",
         row("distinct characters (initial vocabulary, incl. §)", lambda x: f"{x['characters']:,}"),
         row("merged items", lambda x: f"{x['merges']:,}"),
         row("word-final items (end with §)", lambda x: f"{x['word_final_items']:,}"),
         row("<b>complete tokens</b> (classic token + §)", lambda x: f"<b>{x['complete_tokens']:,}</b>"),
         row("&nbsp;&nbsp;of them: the token occurs &ge; 100 times", lambda x: f"{x['complete_tokens_freq']['100']:,}"),
         row("&nbsp;&nbsp;of them: one letter (e.g. e§, ת§)", lambda x: f"{x['complete_tokens_one_char']:,}"),
         row("word + attached punctuation (e.g. China.§)", lambda x: f"{x['token_plus_punctuation']:,}"),
         row("word-initial / word-internal items (no §)", lambda x: f"{x['inner_items']:,}"),
         "</table>"]
    for l in LANGS:
        p.append(f"<p><b>{l}</b>, first merges: {item_list(r[l]['first_merges'][:30], l)}</p>")
        p.append(f"<p><b>{l}</b>, longest items: {item_list(r[l]['longest_items'][:6], l)}</p>")

    p.append("<h2>1. how many complete tokens are in the vocabulary?</h2>" + bidi(Q1))
    for i, group in ((2, "sensible"), (3, "not sensible"), (4, "both")):
        p.append(f"<h2>{i}. items that {LABELS[group]}</h2>" + bidi(QTEXT[group]))
        for l in LANGS:
            p.append(f"<h3>{l}</h3>" + probe_table(r[l], l, group))
        p.append(bidi(QAFTER.get(group, "")))
    p.append("</body></html>")

    (HERE / "bpe.html").write_text("".join(p), encoding="utf-8")
    browser = next(b for b in BROWSERS if Path(b).exists())
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={HERE / 'bpe.pdf'}", (HERE / "bpe.html").as_uri()], check=True)
    print("wrote", HERE / "bpe.pdf")


INTRO = """
<p>bpe.py implements training as in sennrich et al. (2016, section 3.2): the text is split on whitespace,
every word type becomes its characters plus the end-of-word item <b>§</b>, and the most frequent pair of
adjacent items is merged until the vocabulary has N items. pairs are counted over word types weighted by
their frequency (the efficiency tip), and kept up to date incrementally: an index pair &rarr; words lets each
merge rewrite only the words that contain the pair, and a heap returns the most frequent pair. training takes
about 2-3 minutes per language. punctuation is <i>not</i> removed: bpe sees the raw text, so
"China." is the word <i>China.</i>. a literal § in the files (a few hundred section signs) is treated as
whitespace, so the end-of-word item stays unambiguous.</p>
<p>splits below are produced with the greedy longest-prefix tokenizer of the assignment
(<code>tokenize</code> in bpe.py). pieces are shown as boxes; hebrew reads right to left.</p>
"""

Q1 = """
<p><b>english: 11,191. hebrew: 14,433.</b> a complete token is an item that is a classic token type
(punctuation stripped, as in the unigram part) followed by §, so it covers a whole word on its own: the§,
of§, and§, was§, The§, that§ ... singer-songwriter§, responsibilities§; של§, את§, על§, הוא§, היה§,
שנת§ ... האוניברסיטאות§.</p>
<p>about 37% (english) and 48% (hebrew) of the vocabulary are whole words, and more than half of all
merges in both languages produce word-final items. bpe spends its budget on frequent words first, so a
frequent word ends up as one item and only rarer words are split. hebrew has more complete tokens because
prefixed forms such as המלך, בשנת, והוא are separate whitespace words, and each frequent one becomes its
own item.</p>
<p>the count is an upper bound in one sense: some of these strings are "tokens" only formally. e§, s§, d§
(70 one-letter items in english) and ת§, ה§, ם§, ים§ (98 in hebrew) exist as stray one-letter tokens
in the file, but in the vocabulary they are used almost only as word endings. counting only tokens seen at
least 100 times as standalone words gives 10,389 / 13,066. it is a lower bound in another sense: 3,687 /
3,019 more items are a word with punctuation attached (China.§, Revolution.§, year,§), which bpe learns
because it never separates punctuation from words.</p>
"""

QTEXT = {
    "sensible": """<p>these items are longer than one character, shorter than a whole word, and match a
morpheme: a unit with its own meaning or grammatical function. they are learned because a morpheme is shared
by many different words, so its letters are adjacent very often. in english these are mostly
<b>derivational and inflectional affixes</b> (un-, re-, non-, micro-, -er, -ness, -ation, -ful, -ed, -ing)
and parts of compounds. in hebrew they are mostly the <b>clitic prefixes</b> ו, ה, ב, ל, כ, מ, ש and
their combinations (וב, ול, כש, שה), the <b>plural / feminine endings</b> ים§, ות§, ית§, ת§, and the
hitpa'el verb prefix הת. these are exactly the units that make hebrew have many more types than english
(part b.1), so bpe "rediscovers" them.</p>""",
    "not sensible": """<p>these items are frequent letter sequences, not morphemes. bpe only knows
co-occurrence counts, not meaning, so it merges any pair that is frequent: ic, eber, gs, preh, ret, hin are
leftovers of other words. two mechanisms produce bad splits. (1) <b>bpe merges are not morphemes</b>: an item
such as "real" or "king§" is a frequent word, so it is in the vocabulary even when the word at hand is
re+align or shrink+ing. (2) <b>the greedy longest-prefix tokenizer</b> grabs the longest item at the
start (ret, preh, unc, והס, שבמ, מהמ) and leaves whatever remains, even if a shorter first piece would give
a morphological split. in hebrew the second problem is constant: a word starts with stacked prefixes
(ו+ה+..., ש+ב+...), and the greedy tokenizer glues the prefixes to the first root letters (והס|פרים,
מהמ|משלו|ת), cutting the three-letter root, which is the actual meaning-bearing unit. bpe's units are
concatenative; hebrew's root-and-pattern morphology is not.</p>""",
    "both": """<p>yes. an item is a string; whether it is a morpheme depends on the word it splits. in each
pair below the same item is used in both words, sensible in the first and not in the second.</p>""",
}

QAFTER = {
    "both": """<p><b>-er§</b> is the agent suffix in print|er (also teach-er, sing-er) but only the last two letters
in show|er, mist|er, ci|ph|er. <b>ing§</b> is the progressive suffix in Con|clud|ing but part of a name in
Be|hr|ing, and in shri|n|king§ the word king§ wins. <b>re</b> is "again" in re|heat, while preheat loses its
prefix pre- to the item preh. <b>מות§</b> is the word 'death / to die' in ול|מות, but in וכ|מות the same
split pretends that כ is the prefix 'as' and cuts the stem כמות 'quantity'. <b>שהת</b> is that + hitpa'el
prefix in שהת|מוד|דו but ש + article + a root letter in וכ|שהת|למי|דים. <b>ת§</b> is the feminine ending of
פסיכולוגי|ת but half of the plural ות in מהמ|משלו|ת. even a single prefix letter changes the result:
שבת|ות is split well, while ו+שבתות gives ושב|תות. this ambiguity is inherent: bpe chooses items by
frequency, and the same letters are a morpheme in some words and a coincidence in others.</p>""",
}

CSS = """
body{font-family:Arial,'David',sans-serif;font-size:10.5pt;margin:0;line-height:1.4}
h1{font-size:19pt} h2{font-size:13.5pt;margin-top:16px;border-bottom:1px solid #999}
h3{font-size:11pt;margin:8px 0 3px}
table{border-collapse:collapse;margin:4px 0;width:100%} td,th{border:1px solid #bbb;padding:3px 6px;vertical-align:top;font-size:9.5pt}
th{background:#eee;text-align:left}
.p{display:inline-block;border:1px solid #889;border-radius:3px;padding:0 3px;margin:1px;background:#f4f4fa;white-space:nowrap}
.split{white-space:nowrap} code{font-size:9.5pt}
@page{margin:16mm}
"""

if __name__ == "__main__":
    main()
