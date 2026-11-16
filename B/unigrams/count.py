"""Count token types in a text file (whole file and first half).

Usage:
    python count.py <text file (.txt or .txt.gz)> <output prefix>

Writes:
    <prefix>.counts.tsv   type<TAB>count for the whole file, most frequent first
    <prefix>.half.tsv     same, for the first N/2 tokens only
    <prefix>.meta.json    {"tokens": N, "half": N // 2}

Two passes are made over the file: the first counts all tokens (and so
finds N), the second counts only the first N/2 tokens. This avoids keeping
the whole token sequence in memory.
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

from tokenizer import iter_token_blocks


def count_all(path):
    counts, n = Counter(), 0
    for block in iter_token_blocks(path):
        counts.update(block)
        n += len(block)
    return counts, n


def count_prefix(path, limit):
    counts, n = Counter(), 0
    for block in iter_token_blocks(path):
        block = block[: limit - n]
        counts.update(block)
        n += len(block)
        if n >= limit:
            break
    return counts


def write_counts(counts, path):
    # Sort by descending count, ties broken alphabetically (deterministic ranks).
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    with open(path, "w", encoding="utf-8") as fh:
        for tok, c in items:
            fh.write(f"{tok}\t{c}\n")


def main():
    src, prefix = sys.argv[1], sys.argv[2]
    Path(prefix).parent.mkdir(parents=True, exist_ok=True)

    t = time.time()
    counts, n = count_all(src)
    print(f"[{src}] pass 1: {n:,} tokens, {len(counts):,} types ({time.time() - t:.0f}s)")
    write_counts(counts, prefix + ".counts.tsv")
    del counts

    t = time.time()
    half = count_prefix(src, n // 2)
    print(f"[{src}] pass 2: first {n // 2:,} tokens, {len(half):,} types ({time.time() - t:.0f}s)")
    write_counts(half, prefix + ".half.tsv")

    with open(prefix + ".meta.json", "w") as fh:
        json.dump({"tokens": n, "half": n // 2}, fh)


if __name__ == "__main__":
    main()
