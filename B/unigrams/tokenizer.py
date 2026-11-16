"""Tokenization shared by the unigram scripts.

Token definition (assignment, part B): a maximal sequence of characters that
are neither whitespace nor punctuation. Punctuation at the edges of a
whitespace-separated chunk is stripped, word-internal punctuation is kept:

    "they ate apples, and then, they ate some ice-cream!!"
    -> they ate apples and then they ate some ice-cream

"Punctuation" here means every Unicode character in category P* (punctuation)
or S* (symbols such as = + $ |), plus control characters (Cc). Hebrew niqqud
(category Mn) is NOT punctuation and stays part of the token.

Invisible format characters (Cf, e.g. the right-to-left mark common in
Hebrew text, or zero-width spaces) are deleted before tokenizing; otherwise
they would create spurious types that look identical to real ones.
"""
import gzip
import re
import sys
import unicodedata

_PUNCT_CATEGORIES = ("P", "S", "Cc")
_FORMAT_CATEGORIES = ("Cf",)
BLOCK_SIZE = 1 << 26  # 64 MB of text per regex call


def _char_class(categories):
    """Build the body of a regex character class for the given categories."""
    ranges, start, prev = [], None, None
    for cp in range(sys.maxunicode + 1):
        cat = unicodedata.category(chr(cp))
        if cat.startswith(categories) and not chr(cp).isspace():
            if start is None:
                start = cp
            elif cp != prev + 1:
                ranges.append((start, prev))
                start = cp
            prev = cp
    ranges.append((start, prev))
    esc = lambda cp: "\\U%08x" % cp
    return "".join(esc(a) if a == b else esc(a) + "-" + esc(b) for a, b in ranges)


_P = _char_class(_PUNCT_CATEGORIES)
FORMAT_RE = re.compile("[%s]+" % _char_class(_FORMAT_CATEGORIES))
# A token: content chars, optionally joined by internal punctuation runs.
# Content = not whitespace and not punctuation, so a token never crosses
# whitespace and never starts or ends with punctuation.
TOKEN_RE = re.compile(r"[^\s%s]+(?:[%s]+[^\s%s]+)*" % (_P, _P, _P))


def tokenize(text):
    """Return the list of tokens in a string."""
    return TOKEN_RE.findall(FORMAT_RE.sub("", text))


def _open(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def iter_token_blocks(path):
    """Yield lists of tokens, in file order, reading the file in large blocks.

    Each block is cut at its last whitespace so that no token is split
    between two blocks.
    """
    tail = ""
    with _open(path) as fh:
        while True:
            chunk = fh.read(BLOCK_SIZE)
            if not chunk:
                break
            text = tail + chunk
            cut = max(text.rfind(" "), text.rfind("\n"))
            if cut == -1:
                tail = text
                continue
            text, tail = text[:cut], text[cut:]
            yield tokenize(text)
    if tail:
        yield tokenize(tail)


if __name__ == "__main__":
    sample = "they ate apples, and then, they ate some ice-cream!!"
    print(tokenize(sample))
