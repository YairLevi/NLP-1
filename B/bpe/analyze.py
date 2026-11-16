"""Inspect the learned BPE vocabularies (numbers and examples for bpe.pdf).

Usage: python analyze.py
Reads  out/<lang>.vocab.txt                   (written by bpe.py)
       ../unigrams/out/<lang>.counts.tsv     (classic token types and counts, part B.1)
Writes out/<lang>.analysis.json, read by build_pdf.py, and prints a summary.

A vocabulary item is a "complete token" when it is a classic token type (the
punctuation-stripped definition of the unigram part) followed by the
end-of-word item, e.g. "the§": the item covers one whole word.
"""
import json
import unicodedata
from pathlib import Path

from bpe import EOW, tokenize

HERE = Path(__file__).resolve().parent
LANGS = ("english", "hebrew")

# Words split with the greedy tokenizer to show items in context (Q2-Q4).
# Grouped by the question they illustrate; build_pdf.py prints the groups.
PROBES = {
    "english": {
        "sensible": ["unfair", "untie", "reheat", "kindness", "printer", "smoothed",
                     "colouration", "nonmetal", "micrometres", "helpful", "photographers",
                     "Concluding", "underdog", "mountaintop", "crossbow"],
        "not sensible": ["rethinking", "preheat", "icebergs", "leggings", "slippery",
                         "isomers", "juices", "cohesive", "vegetables", "realign",
                         "uncomfortable", "betrothed", "Behring"],
        "both": ["printer", "shower", "mister", "cipher",
                 "Concluding", "Behring", "shrinking",
                 "reheat", "preheat",
                 "unfair", "unify"],
    },
    "hebrew": {
        "sensible": ["כשהמלכה", "ובחנות", "כשחנות", "ולבנים", "ולראות", "שבתות", "ביתית",
                     "פסיכולוגית", "שהתמודדו", "התכתבויות"],
        "not sensible": ["והספרים", "ובספרייה", "שבמדינות", "מהממשלות", "כתבתם",
                         "הכתובות", "והמשוררת", "מירושלים", "לחנות", "ולחם", "תלמידה",
                         "ושבתות", "ולשתות"],
        "both": ["ולמות", "וכמות",
                 "שהתמודדו", "וכשהתלמידים",
                 "פסיכולוגית", "מהממשלות"],
    },
}


def load_type_counts(lang):
    """Classic token type -> count, from the unigram part."""
    counts = {}
    with open(HERE.parent / "unigrams" / "out" / f"{lang}.counts.tsv", encoding="utf-8") as fh:
        for line in fh:
            tok, c = line.rstrip("\n").split("\t")
            counts[tok] = int(c)
    return counts


def strip_punct(s):
    """Remove punctuation and symbols from both ends (as the classic tokenizer does)."""
    i, j = 0, len(s)
    while i < j and unicodedata.category(s[i])[0] in "PS":
        i += 1
    while j > i and unicodedata.category(s[j - 1])[0] in "PS":
        j -= 1
    return s[i:j]


def analyze(lang):
    vocab = (HERE / "out" / f"{lang}.vocab.txt").read_text(encoding="utf-8").split("\n")[:-1]
    items = set(vocab)
    types = load_type_counts(lang)
    n_chars = next(i for i, s in enumerate(vocab) if len(s) > 1)   # merged items start here
    merges = vocab[n_chars:]

    final = [s[:-1] for s in merges if s.endswith(EOW)]            # stems of word-final items
    complete = [x for x in final if x in types]
    with_punct = [x for x in final if x not in types and strip_punct(x) in types]
    inner = [s for s in merges if not s.endswith(EOW)]             # word-initial / medial items

    report = {
        "vocab_size": len(vocab),
        "characters": n_chars,
        "merges": len(merges),
        "word_final_items": len(final),
        "complete_tokens": len(complete),
        "complete_tokens_freq": {th: sum(types[x] >= th for x in complete) for th in (10, 100, 1000)},
        "complete_tokens_one_char": sum(len(x) == 1 for x in complete),
        "complete_tokens_examples": [x + EOW for x in complete[20:40]],
        "token_plus_punctuation": len(with_punct),
        "token_plus_punctuation_examples": [x + EOW for x in with_punct[:15]],
        "inner_items": len(inner),
        "first_merges": merges[:40],
        "last_merges": merges[-25:],
        "longest_items": sorted(merges, key=len, reverse=True)[:10],
        "probes": {group: {w: tokenize(w, items) for w in words}
                   for group, words in PROBES[lang].items()},
    }
    (HERE / "out" / f"{lang}.analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def main():
    for lang in LANGS:
        r = analyze(lang)
        print(f"== {lang}: {r['vocab_size']} items = {r['characters']} characters + {r['merges']} merges")
        print(f"   word-final items: {r['word_final_items']}, complete tokens: {r['complete_tokens']} "
              f"(type freq >= 10/100/1000: {r['complete_tokens_freq']}), "
              f"one-letter: {r['complete_tokens_one_char']}")
        print(f"   token + attached punctuation: {r['token_plus_punctuation']}, other items: {r['inner_items']}")
        for group, splits in r["probes"].items():
            print(f"   [{group}] " + " | ".join(f"{w}: {' '.join(s)}" for w, s in splits.items()))


if __name__ == "__main__":
    main()
