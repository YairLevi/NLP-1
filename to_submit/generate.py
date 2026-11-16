from collections import defaultdict
import random

class PCFG(object):
    def __init__(self):
        self._rules = defaultdict(list)
        self._sums = defaultdict(float)

    def add_rule(self, lhs, rhs, weight):
        assert(isinstance(lhs, str))
        assert(isinstance(rhs, list))
        self._rules[lhs].append((rhs, weight))
        self._sums[lhs] += weight

    @classmethod
    def from_file(cls, filename):
        grammar = PCFG()
        with open(filename) as fh:
            for line in fh:
                line = line.split("#")[0].strip()
                if not line: continue
                w,l,r = line.split(None, 2)
                r = r.split()
                w = float(w)
                grammar.add_rule(l,r,w)
        return grammar

    def is_terminal(self, symbol): return symbol not in self._rules

    def gen(self, symbol):
        if self.is_terminal(symbol): return symbol
        else:
            expansion = self.random_expansion(symbol)
            return " ".join(self.gen(s) for s in expansion)

    def random_sent(self):
        return self.gen("ROOT")

    def gen_tree(self, symbol):
        """
        Generates a random derivation tree rooted at symbol.
        A tree is a terminal string, or a tuple (symbol, [child trees]).
        """
        if self.is_terminal(symbol): return symbol
        expansion = self.random_expansion(symbol)
        return (symbol, [self.gen_tree(s) for s in expansion])

    def random_tree(self):
        return self.gen_tree("ROOT")

    @staticmethod
    def format_tree(tree, indent=0):
        """
        Pretty-prints a tree in bracketed form. A node whose children are all
        terminals goes on one line; otherwise each child gets its own line,
        aligned under the first child.
        """
        if isinstance(tree, str): return tree
        symbol, children = tree
        label = "(" + symbol + " "
        if all(isinstance(c, str) for c in children):
            return label + " ".join(children) + ")"
        pad = indent + len(label)
        parts = [PCFG.format_tree(c, pad) for c in children]
        return label + ("\n" + " " * pad).join(parts) + ")"

    def random_expansion(self, symbol):
        """
        Generates a random RHS for symbol, in proportion to the weights.
        """
        p = random.random() * self._sums[symbol]
        for r,w in self._rules[symbol]:
            p = p - w
            if p < 0: return r
        return r


if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser(description="Generate random sentences from a PCFG.")
    parser.add_argument("grammar", type=str, help="path to grammar file")
    parser.add_argument("-n", type=int, default=1, help="number of lines to generate (default: 1)")
    parser.add_argument("-t", action="store_true", help="print the derivation tree instead of just the sentence")
    args = parser.parse_args()

    pcfg = PCFG.from_file(args.grammar)
    for i in range(args.n):
        if args.t:
            print(PCFG.format_tree(pcfg.random_tree()))
        else:
            print(pcfg.random_sent())
