"""Frequent n-grams (frequency > 1) of a text file, memory-light.

Usage:
    python ngrams.py <text file (.txt or .txt.gz)> <language name> [out dir]

Writes into <out dir> (default: out/ next to this script):
    <lang>.tokens.npy   cache: every token of the file as an int32 type id
    <lang>.vocab.txt    cache: type id -> token string (one per line)
    <lang>.ngrams.json  results: per-level stats, top-10 5-/10-grams,
                        longest repeated n-gram(s)

Idea (the assignment hint, applied level by level, a.k.a. Apriori)
------------------------------------------------------------------
An n-gram can occur more than once only if its prefix (n-1)-gram *and* its
suffix (n-1)-gram occur more than once. So we never count all n-grams: at
level n we only look at positions where the (n-1)-gram starting there is
already known to be frequent, and extend it by one token.

    level 1 : positions whose token type occurs > 1 time
    level n : positions p that survive level n-1, whose suffix (the
              (n-1)-gram at p+1) also survived, extended by token p+n-1;
              keep only the extensions that occur > 1 time.

The survivor set shrinks fast, so the expensive levels are the first two.
We stop at the first level with no survivor: the previous level holds the
longest repeated n-grams.

Memory tricks
-------------
* tokens are int32 ids in one numpy array (63M tokens = 250 MB), no strings;
* an n-gram is never materialised: it is a group id (int32) for each
  surviving start position, built from (id of its (n-1)-prefix, last token)
  and counted with one np.unique over int64 keys;
* only 2 numpy arrays (positions, group ids) of the previous level are kept;
* tokenizing is the slow part, so the token array is cached on disk and
  reused by later runs.

n-grams are taken over the file as one token stream (line breaks are not
boundaries), exactly as the assignment defines an n-gram: n consecutive tokens.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "unigrams"))
from tokenizer import iter_token_blocks  # noqa: E402  (same token definition as Part B unigrams)

REPORT_N = (5, 10)  # levels for which the top-10 list is reported
TOP = 10
SEQ_MAX = 32   # exact level-by-level search up to this n, hashing search beyond
LONGEST_SHOWN = 5   # at most this many longest n-grams are listed


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- caching --
def load_or_build_tokens(src, lang, out):
    """Return (tokens int32 array, vocab list); tokenize only on a cache miss."""
    tok_path, voc_path = out / f"{lang}.tokens.npy", out / f"{lang}.vocab.txt"
    if tok_path.exists() and voc_path.exists():
        log(f"cache hit: {tok_path.name}")
        with open(voc_path, encoding="utf-8") as fh:
            vocab = fh.read().split("\n")[:-1]
        return np.load(tok_path), vocab

    vocab_ids, parts = {}, []
    for block in iter_token_blocks(src):
        ids = [vocab_ids.setdefault(t, len(vocab_ids)) for t in block]
        parts.append(np.array(ids, dtype=np.int32))
        log(f"tokenized {sum(map(len, parts)):,} tokens, {len(vocab_ids):,} types")
    tokens = np.concatenate(parts)
    vocab = list(vocab_ids)
    out.mkdir(parents=True, exist_ok=True)
    np.save(tok_path, tokens)
    with open(voc_path, "w", encoding="utf-8") as fh:
        fh.write("".join(t + "\n" for t in vocab))
    return tokens, vocab


# ------------------------------------------------------------- the search --
def decode(tokens, vocab, pos, n):
    return " ".join(vocab[t] for t in tokens[pos:pos + n])


def top_groups(pos, gid, cnt, k):
    """First-occurrence positions of the k most frequent groups.

    Ties are broken by first occurrence in the file (pos is sorted)."""
    _, first = np.unique(gid, return_index=True)  # pos increasing -> first occurrence
    first_pos = pos[first]                        # indexed by group id
    order = np.lexsort((first_pos, -cnt))
    return [(int(first_pos[g]), int(cnt[g])) for g in order[:k]]


def find_ngrams(tokens, vocab):
    n_tok, v = len(tokens), len(vocab)
    freq1 = np.bincount(tokens, minlength=v) > 1
    log(f"{n_tok:,} tokens, {v:,} types, {int(freq1.sum()):,} types occur > 1 time")
    # Hint: a singleton token can be in no repeated n-gram -> mark it -1.
    raw = tokens
    tokens = np.where(freq1[tokens], tokens, -1).astype(np.int32)

    # level 1: start positions of frequent tokens; group id = type id
    pos = np.flatnonzero(tokens >= 0)
    gid = tokens[pos].astype(np.int64)
    cnt = np.bincount(gid, minlength=v)
    levels = [{"n": 1, "grams": int(freq1.sum()), "positions": int(len(pos))}]
    result = {"tokens": int(n_tok), "levels": levels, "top": {}}
    n = 1
    while n < SEQ_MAX:
        # candidates for level m = n+1: survivors of level n extended by one token
        m = n + 1
        ok = pos + n < n_tok
        cpos, cgid = pos[ok], gid[ok]
        ext = tokens[cpos + n]
        ok = ext >= 0  # extension token is frequent
        if m >= 3:     # suffix (m-1)-gram at p+1 must have survived level m-1
            at = np.minimum(np.searchsorted(pos, cpos + 1), len(pos) - 1)
            ok &= pos[at] == cpos + 1
        cpos, cgid, ext = cpos[ok], cgid[ok], ext[ok]
        if len(cpos) == 0:
            break
        key = cgid * v + ext  # (prefix group, last token) -> one int64
        _, inv, cnt_all = np.unique(key, return_inverse=True, return_counts=True)
        del key, cgid, ext
        keep = cnt_all > 1
        if not keep.any():
            break
        sel = keep[inv]
        gid = (np.cumsum(keep) - 1)[inv[sel]]
        pos, cnt, n = cpos[sel], cnt_all[keep], m
        del cpos, inv, sel, keep, cnt_all
        levels.append({"n": n, "grams": int(len(cnt)), "positions": int(len(pos))})
        log(f"n={n}: {len(cnt):,} repeated n-grams, {len(pos):,} positions")
        if n in REPORT_N:
            result["top"][str(n)] = [
                {"ngram": decode(tokens, vocab, p, n), "count": c}
                for p, c in top_groups(pos, gid, cnt, TOP)
            ]

    if n == SEQ_MAX:  # still repeated at SEQ_MAX: switch to the fast long-n search
        n, groups = longest_by_hash(raw, pos)
        result["longest"] = {"n": n, "how_many": len(groups), "examples": [
            {"ngram": decode(raw, vocab, p, n), "count": c} for p, c in groups[:LONGEST_SHOWN]]}
    else:
        result["longest"] = {"n": n, "how_many": int(len(cnt)), "examples": [
            {"ngram": decode(tokens, vocab, p, n), "count": c}
            for p, c in top_groups(pos, gid, cnt, LONGEST_SHOWN)]}
    return result


# ------------------------------------------- long n-grams: hashing search --
def window_hashes(S, binv_pow, pos, n):
    """64-bit polynomial hash of the n-gram at each position (equal gram -> equal hash)."""
    return (S[pos + n] - S[pos]) * binv_pow


def longest_by_hash(raw, pos):
    """Longest repeated n-gram, starting from survivors `pos` of level SEQ_MAX.

    Level-by-level extension costs one pass per n, hopeless when the file
    holds repeated passages thousands of tokens long. Instead:
      * S = prefix sums of token * B^i (mod 2^64) gives the hash of any window
        in O(1): hash(p, n) = (S[p+n]-S[p]) * B^-p;
      * "does a repeated n-gram exist?" is monotone in n, so exponential then
        binary search on n, each test = np.unique over the survivors' hashes;
      * the answer is verified token by token, so hash collisions cannot
        change the result.
    """
    n_tok = len(raw)
    B = np.uint64(0x9E3779B97F4A7C15)               # odd => invertible mod 2^64
    binv = np.uint64(pow(int(B), -1, 1 << 64))
    log("building prefix hash array")
    # powers of B by cumulative product (wraps mod 2^64), then weighted prefix sums
    w = np.empty(n_tok, dtype=np.uint64)
    w[0] = 1
    if n_tok > 1:
        w[1:] = B
        np.cumprod(w, out=w)                        # w[i] = B^i
    w *= (raw.astype(np.uint64) + np.uint64(1))     # token ids +1: never 0
    S = np.zeros(n_tok + 1, dtype=np.uint64)
    np.cumsum(w, out=S[1:])
    del w
    # B^-p for the survivor positions, by vectorised square-and-multiply
    binv_pow = np.ones(len(pos), dtype=np.uint64)
    base, e = np.full(len(pos), binv, dtype=np.uint64), pos.astype(np.uint64)
    for _ in range(int(n_tok).bit_length()):
        odd = (e & np.uint64(1)).astype(bool)
        binv_pow[odd] *= base[odd]
        base *= base
        e >>= np.uint64(1)

    def repeated(n):
        ok = pos + n <= n_tok
        h = window_hashes(S, binv_pow[ok], pos[ok], n)
        u, cnt = np.unique(h, return_counts=True)
        return bool((cnt > 1).any())

    lo, hi = SEQ_MAX, SEQ_MAX * 2                   # lo: repeated, hi: candidate
    while repeated(hi):
        lo, hi = hi, hi * 2
        log(f"repeated n-gram of length {lo} exists")
    while hi - lo > 1:                              # lo repeated, hi not
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if repeated(mid) else (lo, mid)
    n = lo
    log(f"longest repeated n-gram: n={n}")

    ok = pos + n <= n_tok
    p_ok = pos[ok]
    h = window_hashes(S, binv_pow[ok], p_ok, n)
    order = np.argsort(h, kind="stable")            # stable: keeps file order in a group
    h_sorted, p_sorted = h[order], p_ok[order]
    cut = np.flatnonzero(np.diff(h_sorted)) + 1
    groups = []
    for g in np.split(p_sorted, cut):
        if len(g) < 2:
            continue
        first = raw[g[0]:g[0] + n]                  # exact verification
        same = [int(q) for q in g if np.array_equal(raw[q:q + n], first)]
        if len(same) > 1:
            groups.append((same[0], len(same)))
    groups.sort(key=lambda x: (-x[1], x[0]))
    return n, groups


def main():
    src, lang = sys.argv[1], sys.argv[2]
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE / "out"
    t0 = time.time()
    tokens, vocab = load_or_build_tokens(src, lang, out)
    log(f"tokens ready ({time.time() - t0:.0f}s)")
    result = find_ngrams(tokens, vocab)
    with open(out / f"{lang}.ngrams.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    log(f"done in {time.time() - t0:.0f}s; longest repeated n-gram: n={result['longest']['n']}")


if __name__ == "__main__":
    main()
