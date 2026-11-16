"""Byte-pair encoding (BPE) sub-word vocabulary: training and greedy tokenization.

Training follows Sennrich, Haddow & Birch (2016), "Neural Machine Translation of
Rare Words with Subword Units", Section 3.2, with the conventions of the
assignment:

* Whitespace separates words. Every run of whitespace is one end-of-word item,
  written ``§``. It is appended to the end of each word, so it can merge with
  the item *before* it but never with an item after it. Vocabulary items
  therefore never cross word boundaries, and ``§`` appears in an item either
  alone or as its last character.
* The vocabulary starts as all distinct characters of the file (plus ``§``).
  Each round merges the most frequent pair of adjacent items into one new item,
  until the vocabulary has exactly N items.

Efficiency (the paper's "dictionary" trick plus its "index all pairs, update
incrementally" remark):

* The text is reduced once to a dictionary ``word -> frequency``. Pair counts
  are taken over word types, each weighted by its frequency, never over the
  running text.
* Pair counts are kept up to date between rounds instead of being recounted.
  An inverted index ``pair -> word types containing it`` limits each merge to
  the words that actually contain the pair.
* A max-heap with lazy deletion returns the most frequent pair in O(log P).

Usage as a module::

    from bpe import train_bpe
    vocab = train_bpe("english.txt", 30000)

Usage as a script::

    python bpe.py english.txt 30000 -o english.vocab.txt
"""
import argparse
import heapq
import logging
from array import array
from collections import Counter, defaultdict

EOW = "§"                 # end-of-word item that stands for any run of whitespace
READ_BLOCK = 1 << 24      # characters read from the file per step (16M)

log = logging.getLogger("bpe")


# ---------------------------------------------------------------------------
# Step 1: text -> word-type frequencies
# ---------------------------------------------------------------------------

def count_words(filename):
    """Return a Counter ``word -> frequency`` over whitespace-separated words.

    The file is read in blocks; each block is cut at its last whitespace so
    that no word is split between two blocks.

    A literal ``§`` in the text would be indistinguishable from the end-of-word
    item, and could produce items with ``§`` in the middle or at the start.
    It is a rare symbol (the section sign), so it is treated like whitespace:
    it ends the current word.
    """
    counts = Counter()
    tail = ""
    with open(filename, encoding="utf-8") as fh:
        while True:
            block = fh.read(READ_BLOCK)
            if not block:
                break
            text = tail + block
            cut = _last_whitespace(text)
            text, tail = text[:cut], text[cut:]
            counts.update(text.replace(EOW, " ").split())
    counts.update(tail.replace(EOW, " ").split())
    return counts


def _last_whitespace(text):
    """Index of the last whitespace character in text (0 if there is none)."""
    for i in range(len(text) - 1, -1, -1):
        if text[i].isspace():
            return i
    return 0


# ---------------------------------------------------------------------------
# Step 2: BPE merges over the word-type dictionary
# ---------------------------------------------------------------------------

class _PairStats:
    """Pair frequencies with fast "most frequent pair" lookup.

    ``counts[pair]`` is the exact current frequency. The heap holds
    ``(-count, pair)`` snapshots; an entry is stale when its count no longer
    equals ``counts[pair]`` and is skipped when it reaches the top (lazy
    deletion). Ties are broken by the smaller pair of item ids, which makes
    training deterministic.
    """

    def __init__(self, counts):
        self.counts = counts
        self.heap = [(-c, p) for p, c in counts.items()]
        heapq.heapify(self.heap)

    def add(self, deltas):
        """Apply ``pair -> change`` and push the new value of each changed pair."""
        for pair, d in deltas.items():
            if d == 0:
                continue
            c = self.counts.get(pair, 0) + d
            if c > 0:
                self.counts[pair] = c
                heapq.heappush(self.heap, (-c, pair))
            else:
                self.counts.pop(pair, None)

    def pop_best(self):
        """Return ``(pair, count)`` of the most frequent pair, or None if none left."""
        while self.heap:
            neg, pair = heapq.heappop(self.heap)
            if self.counts.get(pair) == -neg:
                del self.counts[pair]       # it is about to be merged away
                return pair, -neg
        return None


def _merge_word(symbols, a, b, new):
    """Replace every non-overlapping occurrence of ``a b`` (left to right) with ``new``."""
    out = []
    i, n = 0, len(symbols)
    while i < n:
        if i + 1 < n and symbols[i] == a and symbols[i + 1] == b:
            out.append(new)
            i += 2
        else:
            out.append(symbols[i])
            i += 1
    return out


def _learn(word_counts, n_items):
    """Run BPE on a ``word -> frequency`` dict and return the vocabulary (strings).

    Items are handled as integer ids (``vocab[id]`` is the string), so a word is
    a list of small ints and a pair is a tuple of two ints. This keeps memory
    low for millions of word types and makes hashing fast.
    """
    # Initial vocabulary: every character, plus the end-of-word item.
    chars = set(EOW)
    for w in word_counts:
        chars.update(w)
    vocab = sorted(chars)
    if n_items <= len(vocab):
        raise ValueError(f"N={n_items} must be larger than the {len(vocab)} distinct characters")
    item_id = {s: i for i, s in enumerate(vocab)}
    eow = item_id[EOW]

    # Words as item-id lists ending with EOW; their frequencies; pair statistics;
    # inverted index pair -> word ids (array of int32: 4 bytes per entry).
    words = []
    freqs = array("q")
    pair_counts = defaultdict(int)
    where = defaultdict(lambda: array("i"))
    for wid, (w, f) in enumerate(word_counts.items()):
        symbols = [item_id[c] for c in w]
        symbols.append(eow)
        words.append(symbols)
        freqs.append(f)
        for pair in set(zip(symbols, symbols[1:])):
            where[pair].append(wid)
        for pair in zip(symbols, symbols[1:]):
            pair_counts[pair] += f
    stats = _PairStats(dict(pair_counts))
    del pair_counts
    log.info("%d word types, %d characters, %d distinct pairs", len(words), len(vocab), len(stats.counts))

    while len(vocab) < n_items:
        best = stats.pop_best()
        if best is None:
            log.warning("no pairs left: stopping at %d items (asked for %d)", len(vocab), n_items)
            break
        (a, b), count = best
        new = len(vocab)
        vocab.append(vocab[a] + vocab[b])

        # Rewrite only the words that contain the pair, collecting the change
        # in every pair count. Pairs not touching the merge cancel out (-f, +f).
        deltas = defaultdict(int)
        for wid in set(where.pop((a, b), ())):
            old = words[wid]
            merged = _merge_word(old, a, b, new)
            if len(merged) == len(old):
                continue                    # stale index entry: pair no longer here
            f = freqs[wid]
            for pair in zip(old, old[1:]):
                deltas[pair] -= f
            for pair in zip(merged, merged[1:]):
                deltas[pair] += f
                if new in pair:
                    where[pair].append(wid)
            words[wid] = merged
        deltas.pop((a, b), None)            # already removed by pop_best
        stats.add(deltas)

        if len(vocab) % 1000 == 0:
            log.info("%6d items | last merge %r + %r (freq %d)", len(vocab), vocab[a], vocab[b], count)
    return vocab


def train_bpe(filename, N):
    """Train BPE on a UTF-8 text file and return a list of N vocabulary strings.

    The list holds the initial characters (sorted by code point, including the
    end-of-word item ``§``) followed by the merged items in the order learned.
    """
    word_counts = count_words(filename)
    log.info("read %s: %d tokens, %d word types", filename, sum(word_counts.values()), len(word_counts))
    return _learn(word_counts, N)


# ---------------------------------------------------------------------------
# Inference: greedy longest-prefix tokenization
# ---------------------------------------------------------------------------

def tokenize(text, vocab):
    """Split text into vocabulary items, greedily taking the longest prefix.

    Each whitespace-separated word gets ``§`` appended and is split on its own,
    since no item crosses a word boundary. A character not in the vocabulary
    becomes a one-character item. Pass the vocabulary as a set when calling
    this many times, so it is not rebuilt on every call.

    The assignment's example, with the items ``g§`` and ``f§`` added to its
    vocabulary (its expected output uses them; a trained vocabulary always
    has such word-final items):

    >>> tokenize("abcdefg abfbcdef", "abc ab de bcde a b c d e f g g§ f§".split())
    ['abc', 'de', 'f', 'g§', 'ab', 'f', 'bcde', 'f§']
    """
    items = vocab if isinstance(vocab, (set, frozenset)) else set(vocab)
    longest = max(map(len, items))
    out = []
    for word in text.replace(EOW, " ").split():
        s = word + EOW
        i = 0
        while i < len(s):
            for j in range(min(len(s), i + longest), i, -1):
                if s[i:j] in items or j == i + 1:
                    out.append(s[i:j])
                    i = j
                    break
    return out


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("filename", help="UTF-8 text file to train on")
    parser.add_argument("N", type=int, nargs="?", default=30000, help="vocabulary size (default 30000)")
    parser.add_argument("-o", "--output", help="write the vocabulary here, one item per line")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    vocab = train_bpe(args.filename, args.N)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write("\n".join(vocab) + "\n")
        log.info("wrote %d items to %s", len(vocab), args.output)
    else:
        print("\n".join(vocab))


if __name__ == "__main__":
    main()
