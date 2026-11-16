// Builds pdf/cfg.docx (the Part A report) with docx-js.
//
// Usage (from a folder where `npm install docx` was run):
//   node build_cfg.js <output.docx> <repo root>
// Sample sentences and trees are read from A.1/, A.2/, A.3/ and A.4/ in the repo.
// cfg.pdf is then exported from the docx with Word (File > Save As > PDF).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, AlignmentType, LevelFormat, BorderStyle, ShadingType, PageBreak,
} = require("docx");

const OUT = process.argv[2];
const REPO = process.argv[3];
const read = (p) => fs.readFileSync(path.join(REPO, p), "utf8");

// ---------- inline markup: `code`, **bold**, *italic* ----------
function runs(text, base = {}) {
  // "\*" is a literal asterisk (the ungrammaticality mark), kept out of the markup scan.
  const STAR = "\u0001";
  text = text.replace(/\\\*/g, STAR);
  const lit = (s) => s.split(STAR).join("*");
  const out = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: lit(text.slice(last, m.index)), ...base }));
    const t = m[0];
    if (t.startsWith("`")) out.push(new TextRun({ text: lit(t.slice(1, -1)), font: "Consolas", size: 19, ...base }));
    else if (t.startsWith("**")) out.push(new TextRun({ text: lit(t.slice(2, -2)), bold: true, ...base }));
    else out.push(new TextRun({ text: lit(t.slice(1, -1)), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: lit(text.slice(last)), ...base }));
  return out;
}
const LEFT = AlignmentType.LEFT;

const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const P = (t, opts = {}) => new Paragraph({ children: runs(t), alignment: LEFT, spacing: { after: 120 }, ...opts });
const Q = (t) => new Paragraph({
  children: runs(t, { italics: true, color: "444444" }), alignment: LEFT,
  spacing: { after: 120 }, indent: { left: 360 },
  border: { left: { style: BorderStyle.SINGLE, size: 12, color: "999999", space: 8 } },
});
const bullets = (items) => items.map((t) => new Paragraph({
  children: runs(t), alignment: LEFT, numbering: { reference: "bullets", level: 0 }, spacing: { after: 60 },
}));
let numId = 0;
const numbered = (items) => {
  numId += 1;
  return items.map((t) => new Paragraph({
    children: runs(t), alignment: LEFT, numbering: { reference: "numbers" + numId, level: 0 }, spacing: { after: 60 },
  }));
};
const code = (lines) => lines.map((l, i) => new Paragraph({
  alignment: LEFT,
  children: [new TextRun({ text: l.replace(/\t/g, "    "), font: "Consolas", size: 18 })],
  shading: { type: ShadingType.CLEAR, fill: "F3F3F3", color: "auto" },
  spacing: { before: 0, after: i === lines.length - 1 ? 160 : 0, line: 260 },
  indent: { left: 200 },
}));
const codeBlock = (text) => code(text.replace(/\n$/, "").split("\n"));

function table(header, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (t, isHead) => new TableCell({
    children: [new Paragraph({ children: runs(t, isHead ? { bold: true } : {}), alignment: LEFT, spacing: { after: 0 } })],
    width: { size: 0, type: WidthType.DXA },
    shading: isHead ? { type: ShadingType.CLEAR, fill: "E7E6E6", color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
  });
  const mkRow = (cells, isHead) => new TableRow({
    tableHeader: isHead,
    children: cells.map((c, i) => {
      const tc = cell(c, isHead);
      tc.options.width = { size: widths[i], type: WidthType.DXA };
      return tc;
    }),
  });
  return [new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    rows: [mkRow(header, true), ...rows.map((r) => mkRow(r, false))],
  }), new Paragraph({ spacing: { after: 120 }, children: [] })];
}

// ---------- sample data pulled from the repo ----------
const g1gen = read("A.1/grammar1.gen").trim().split("\n");
const g2gen = read("A.2/grammar2.gen").trim().split("\n");
const g4gen = read("A.4/grammar4.gen").trim().split("\n");
const b3 = read("A.3/b3.gen").trim();
const b3trees = b3.split(/\n(?=\(ROOT)/);

// ---------- document ----------
const children = [];
const add = (...xs) => xs.flat().forEach((x) => children.push(x));

add(new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun("Assignment 1, Part A: Generating Sentences with a CFG")] }));
add(P("Intro to NLP 2026–2027. This report answers every “discuss” and “describe” item of Part A. Section numbers follow the assignment (A.0 to A.4). The accompanying files are `generate.py` (with the `-n` and `-t` switches), `grammar1` / `grammar1.gen`, `grammar2` / `grammar2.gen`, `b3.gen`, and `grammar4` / `grammar4.gen`."));
add(P("Throughout, rules are written as *weight LHS → RHS* and an asterisk marks an ungrammatical sentence (*\\*the president sighed a pickle*). Probabilities quoted for a rule are its weight divided by the total weight of all rules with the same left-hand side, which is exactly how `generate.py` picks an expansion."));

// ======================= A.0 =======================
add(H1("A.0  Generating sentences from a CFG: the -n switch"));
add(P("`generate.py` reads the grammar into a `PCFG` object: a dictionary from each left-hand side to its list of (right-hand side, weight) pairs, plus the sum of weights per left-hand side. `gen(symbol)` returns the symbol itself if no rule rewrites it (a terminal), and otherwise picks one expansion at random in proportion to the weights and recursively generates each symbol of that expansion. A sentence is `gen(\"ROOT\")`."));
add(P("The command-line handling was replaced by `argparse`. The grammar path is a positional argument and `-n` is an optional integer that defaults to 1, so `python generate.py grammar` still prints one sentence. The main loop then runs `n` times and prints each sentence with `print`, which puts every sentence on its own line with no blank lines in between:"));
add(codeBlock(`parser.add_argument("grammar", type=str)
parser.add_argument("-n", type=int, default=1)
parser.add_argument("-t", action="store_true")   # part A.3
args = parser.parse_args()
for i in range(args.n):
    print(pcfg.random_sent())`));

// ======================= A.1 =======================
add(H1("A.1  Weights"));

add(H2("Question 1: why so many long sentences?"));
add(Q("Why does the program generate so many long sentences? Specifically, what grammar rule is responsible for that and why? What is special about this rule?"));
add(P("The rule responsible is `NP → NP PP`. It is **recursive**, since an NP rewrites into a structure containing another NP, and it is also **branching**: the PP must expand through `PP → Prep NP`, which adds a second NP. Each use of the rule therefore replaces one open NP with two."));
add(P("`NP` has only two rules, both with weight 1, so half the time an NP terminates (`Det Noun`) and half the time it produces two new NPs. The expected number of new NPs created by one NP is 2 × ½ = **1**. In the language of branching processes this is a *critical* process: it ends with probability 1, but the expected number of NPs, and so the expected sentence length, is **unbounded**. The resulting length distribution is heavy-tailed. Many sentences are short, but a sizeable minority are extremely long. By contrast, the other recursive rule, `Noun → Adj Noun`, is chosen only 1/6 of the time and produces just one new `Noun`, so it dies out quickly."));
add(P("This is visible in a run of 20,000 sentences from the original grammar: the median sentence has 20 tokens, but the mean is about 276 tokens, the longest sentence has over 30,000 tokens, and 354 generations (1.8%) did not finish at all because the recursion exceeded Python's default stack limit of 1,000 frames."));
add(P("Two properties of CFGs explain this behaviour. First, recursion lets a finite grammar generate sentences of unbounded length, so these long sentences are perfectly grammatical even though they are unnatural. Second, the context-free assumption means each expansion is chosen independently of its context. The grammar has no notion of how long the sentence already is, so `NP → NP PP` is exactly as likely deep inside a long sentence as it is at the start."));

add(H2("Question 2: why are multiple adjectives so rare?"));
add(Q("The grammar allows multiple adjectives, as in “the fine perplexed pickle”. Why do the generated sentences show this so rarely?"));
add(P("Multiple adjectives are possible because `Noun → Adj Noun` is recursive, but they rarely appear because `Noun` has six equally weighted rules and only one of them adds an adjective. The other five rewrite to a terminal and end the expansion. Since each expansion is chosen independently, every additional adjective requires choosing the 1/6 rule again, so the probability falls geometrically: about 1 in 6 nouns gets at least one adjective, and only about 1 in 36 (under 3%) gets two or more. With roughly two to three nouns per typical sentence, an adjective chain like *the fine perplexed pickle* shows up in only a small fraction of the output."));

add(H2("Question 3: which numbers to change"));
add(Q("Which numbers must you modify to fix the problems in (1) and (2), making the sentences shorter and the adjectives more frequent?"));
add(P("Two weights are enough, one per problem. Both are in `grammar1`, with comments next to the changed lines."));
add(table(["Rule", "Old", "New", "Effect"], [
  ["`NP → Det Noun`", "1", "**3**", "P(`NP → NP PP`) drops from 1/2 to 1/4, so one NP now creates on average 2 × ¼ = 0.5 new NPs, which is below 1. The recursion dies out quickly and sentences become short."],
  ["`Noun → Adj Noun`", "1", "**3**", "P(adjective) rises from 1/6 to 3/8, and P(two or more adjectives) from (1/6)² ≈ 3% to (3/8)² ≈ 14%. Chains like *the fine perplexed pickle* become common."],
], [2200, 700, 700, 5400]));
add(P("Problem (1) is fixed because an NP is now much less likely to branch into more NPs, and problem (2) because a `Noun` is now more likely to add an adjective than to end the phrase. The general lesson is that a **recursive rule is controlled by its weight relative to the non-recursive alternatives of the same left-hand side**: the ratio decides whether the expected number of new copies is above or below 1, and that threshold is what separates short output from runaway output."));
add(P("**Verification.** 20,000 sentences were generated from each grammar (the original one and `grammar1`) and measured:"));
add(table(["", "Original grammar", "grammar1"], [
  ["Median / mean sentence length (tokens)", "20 / 276", "11 / 13.3"],
  ["Longest sentence (tokens)", "30,500", "115"],
  ["Generations that overflowed the recursion limit", "354 (1.8%)", "0"],
  ["Mean number of PPs per sentence", "74.2", "1.0"],
  ["Sentences with at least 5 PPs", "44.5%", "4.8%"],
  ["Probability that a noun gets an adjective", "1/6 ≈ 17%", "3/8 ≈ 38%"],
  ["Probability of two or more adjectives on a noun", "≈ 3%", "≈ 14%"],
  ["Sentences with at least one adjective", "64%", "70%"],
], [4600, 2200, 2200]));
add(P("The original grammar's sentence-level adjective figures look high only because its sentences are so long and contain so many nouns. Per noun, which is what the rule weight controls, adjectives are more than twice as likely in `grammar1`. Sentences from `grammar1.gen` show both effects:"));
add(code(g1gen.slice(1, 5)));

add(H2("Question 4: other numeric adjustments for more natural sentences"));
add(Q("What other numeric adjustments can you make to the grammar in order to favor a set of more natural sentences? Experiment and discuss."));
add(P("Equal weights mean every alternative is as likely as every other, which is not how real text looks. The idea behind every adjustment below is to move the weights toward real-world frequencies:"));
add(numbered([
  "**Sentence type.** In everyday language most sentences end with a period and are neither questions nor exclamations. Raising the weight of `ROOT → S .` (for example 8 against 1 and 1) makes plain statements the common case instead of one third of the output.",
  "**Determiners.** Some determiners are far more common than others. With equal weights the output fills up with *every*, giving sentences like *every delicious fine sandwich on every pickled perplexed floor kissed every president in a pickle*. Giving *the* more weight than *a*, and *every* the least (5 / 3 / 1), makes the noun phrases read naturally.",
  "**Prepositions.** The same holds for prepositions: *with*, *on* and *in* are common, *under* is rare (3 / 3 / 3 / 1).",
  "**Adjectives.** Repeated and odd adjectives stand out. *pickled* is much rarer as an adjective than *fine* or *delicious*, so lowering it (and raising the others) gives better-sounding phrases and makes a repeated adjective less likely.",
  "**Nouns and verbs.** Subjects and objects share one `Noun` class, so weights cannot make the subject animate, but they can tilt toward nouns that are fine in both roles (*president*, *chief of staff*) and away from odd ones (*floor*, *pickle*), and toward verbs that fit most arguments (*ate*, *wanted*) and away from *pickled*.",
  "**PP chains.** Lowering `NP → NP PP` further (0.5) removes most of the remaining stacked prepositional phrases.",
]));
add(P("**Experiment.** These adjustments were applied to a copy of `grammar1` (with the weights in parentheses above) and 12 sentences were generated:"));
add(code([
  "every fine perplexed sandwich wanted a chief of staff .",
  "a floor ate a pickle under a delicious chief of staff .",
  "the perplexed president wanted the president .",
  "a pickle wanted a sandwich .",
  "every sandwich kissed a president .",
  "the president pickled a floor .",
  "every floor ate a president .",
  "every pickle pickled the fine perplexed president .",
  "the president kissed the chief of staff .",
  "a president understood a chief of staff .",
  "the president in every fine sandwich wanted the pickled perplexed delicious president .",
  "a floor pickled the sandwich .",
]));
add(P("The sentences are shorter, almost all are statements, *the* dominates, and the adjectives are mostly *fine* and *delicious*. The experiment also shows the **limit of numeric adjustments**: weights can only shift frequencies, never forbid anything. *every floor ate a president* and *every pickle pickled the president* are still produced, because a CFG has no context: the choice of verb knows nothing about the subject, and the choice of a second adjective knows nothing about the first. Stopping those sentences needs structural changes (for example separate animate and inanimate noun classes, or a non-recursive adjective slot), not different numbers. The submitted `grammar1` therefore contains only the two changes required by question 3, so that the effect of each number stays clear."));

// ======================= A.2 =======================
add(H1("A.2  Extending the grammar (grammar2)"));
add(H2("Goal and design"));
add(P("`grammar2` must generate everything `grammar1` generates plus sentences (1)–(10) of the assignment and sentences with similar structure, while respecting each verb's **subcategorization frame** (the number and type of arguments it takes). It need not respect selectional restrictions, so *the sandwich thought that …* is fine, but *\\*the president sighed a pickle* must be impossible. Four design decisions shaped the grammar:"));
add(numbered([
  "**One verb class per subcategorization frame.** `TransVerb`, `IntransVerb`, `SentCompVerb` and `PsychVerb` each have their own VP rules, so every VP rule states exactly which arguments its verb takes. This, and nothing else, is what rules out the ungrammatical sentences.",
  "**Single function words go directly into rules** (`that`, `is`, `very`, `it`), the same way the original grammar writes `is it true that S ?`. A class is introduced only for a word set that has several members or will grow (`Conj` for *and*, *or*, …). This avoids one-word classes such as `Comp`, `Cop` or `Adv`.",
  "**Standard linguistic names** for every class (`ProperNoun`, `PsychVerb`, `PresParticiple`), and a layout like code: a header, one section per phrase type, verb phrases grouped by frame, and the lexicon at the end.",
  "**Every new rule is tagged** in a comment with the number of the assignment sentence it exists for.",
]));

add(H2("Rules added, and why"));
add(table(["Sentence", "Rule(s)", "Why"], [
  ["(1) **Sally** ate a sandwich", "`NP → ProperNoun`", "A proper noun is a complete NP without a determiner. Without this rule the only option would be *the Sally*."],
  ["(2) Sally **and** the president wanted **and** ate a sandwich", "`NP → NP Conj NP`, `TransVerb → TransVerb Conj TransVerb`", "Coordination of noun phrases and of verbs. Both rules are recursive, so three or more conjuncts come for free. Verb coordination is restricted to transitive verbs so that both verbs share the single object; coordinating *sighed and ate* would break one of the frames."],
  ["(3) the president **sighed**", "`VP → IntransVerb`", "Intransitive verbs take no object. Having a separate class is what blocks *\\*sighed a pickle*."],
  ["(7) the president **worked on** every proposal on the desk", "`VP → IntransVerb PP`", "An intransitive verb may be followed by a prepositional phrase. *on the desk* attaches to the object through the existing `NP → NP PP`, so the sentence has the usual PP-attachment ambiguity."],
  ["(4), (10) the president **thought that** S", "`VP → SentCompVerb that S`", "A verb with a **sentential complement** takes a clause, not an NP. The embedded `S` builds its own complete VP, so *\\*thought that a sandwich sighed a pickle* is impossible for the same reason as (3)."],
  ["(5) **it perplexed** the president **that** S", "`NP → it`, `VP → PsychVerb NP that S`", "*perplexed* is an object-experiencer **psych verb**: it takes an object and a *that*-clause. *it* is an expletive subject standing in for the extraposed clause. `NP → it` also gives a general pronoun (*it sighed*)."],
  ["(6) the **very very very** perplexed president", "`Adj → very Adj`", "A degree adverb modifies an adjective; the rule is recursive, so stacking comes for free."],
  ["(8) Sally **is lazy**", "`VP → is Adj`", "Copula followed by an adjective."],
  ["(10) … **is a sandwich**", "`VP → is NP`", "Copula followed by a noun phrase."],
  ["(9) Sally **is eating** a sandwich", "`VP → is PresParticiple NP`", "Progressive aspect: *is* + present participle + its object. The object is obligatory because *eating* is the participle of a transitive verb."],
], [2600, 2600, 3800]));
add(P("**Vocabulary added:** *Sally, and, sighed, worked, thought, perplexed, eating, lazy, desk, proposal*, since the grammar must contain every word of the example sentences. **Weights:** `NP → Det Noun` was raised to 6 and `NP → NP Conj NP` set to 0.5. With two recursive NP rules now (PP attachment and coordination) the non-recursive option needs more weight or the sentences explode in length, exactly as in A.1."));

add(H2("What the grammar does not generate"));
add(P("Because a sentence can be parsed by a grammar if and only if it can be generated by it, the grammar was checked with a small Earley recognizer (`tests/test.py`): every sentence (1)–(10) is generable, and the following subcategorization violations are not:"));
add(code([
  "* the president thought that a sandwich sighed a pickle .",
  "* the president sighed a pickle .",
  "* the president ate .",
  "* Sally sighed and the president sighed a thought .",
]));

add(H2("The bad interaction between (2) and (8)/(9)"));
add(Q("Handling sentences (2) and (8)/(9) can interact in a bad way, to create ungrammatical sentences. Discuss and explain what the problem is."));
add(P("Sentence (2) adds coordination (*and*) of noun phrases, and sentences (8) and (9) add the copula *is*. The copula *is* agrees with a **singular** subject, but a coordinated subject such as *Sally and the president* is **plural** and needs *are*. Since the VP is generated independently of the subject (context-freeness again), the grammar happily produces"));
add(code(["* Sally and the president is lazy .", "* Sally and the president is eating a sandwich .", "* every pickle and the sandwich is a floor ."]));
add(P("as if *is* referred to the union of Sally and the president. The same problem appears with the progressive (*\\*Sally and the president is eating a sandwich*). It does not appear with the past-tense verbs (*ate*, *sighed*, …) because English past tense does not mark number. A CFG can only fix this by making the number part of the category: split `NP` into `NP_sg` and `NP_pl` (a coordination is always `NP_pl`), split `VP` into `VP_sg` and `VP_pl`, and use `S → NP_sg VP_sg | NP_pl VP_pl`, with *is* only in `VP_sg` and *are* only in `VP_pl`. This roughly doubles the NP and VP rules, which is the usual price of agreement in a CFG, and it is not required in this part. (A second, smaller interaction is that `TransVerb → TransVerb Conj TransVerb` must not be extended to the copula, since *\\*Sally is and ate a sandwich* has no shared object.)"));

add(H2("Other remarks"));
add(bullets([
  "The assignment writes sentence (10) with a lowercase *sally*; the grammar has only `Sally` (proper nouns are capitalised consistently).",
  "`PsychVerb` accepts any subject, not only the expletive *it*, so the stilted but grammatical *Sally perplexed the president that …* is possible. A stricter variant would be `S → it PsychVerb NP that S`.",
  "The first version of `grammar2` had 14 new rules and 11 new classes (`CP`, `Comp`, `Cop`, `Pron`, `Adv`, `VPing`, …). It was reduced to 12 rules and 5 new classes with the same coverage.",
]));
add(P("Sample sentences from `grammar2.gen` (20 in the file) that show the new constructions:"));
add(code([g2gen[0], g2gen[1], g2gen[4], g2gen[10], g2gen[18], g2gen[13]]));

// ======================= A.3 =======================
add(H1("A.3  Tree structures: the -t switch"));
add(P("With `-t`, `generate.py` prints the derivation tree of each sentence in bracketed form instead of the flat sentence. The flag works together with `-n`, so `python generate.py grammar -n 5 -t` prints five trees. Three small additions to the program were needed:"));
add(bullets([
  "`gen_tree(symbol)` is the same recursion as `gen`, but instead of joining strings it returns a tree: a terminal stays a plain string, and a nonterminal becomes the tuple `(symbol, [child trees])`.",
  "`format_tree(tree, indent)` pretty-prints the tree. A node whose children are all terminals goes on one line, for example `(Noun chief of staff)`. Otherwise each child goes on its own line, aligned under the first child; the indent of a child is the parent's indent plus the length of `\"(\" + symbol + \" \"`.",
  "The `-t` flag is an `argparse` `store_true` option, and the main loop prints `format_tree(random_tree())` instead of `random_sent()`.",
]));
add(P("Building the tree first and formatting it second keeps generation and printing separate, which makes the alignment trivial to compute. The sentence itself is still the sequence of leaves, so `-t` never changes which sentences are generated. `b3.gen` holds five trees generated from `grammar2`; one of them:"));
add(codeBlock(b3trees[2]));
add(P("The tree shows directly which rules were used: `VP → PsychVerb NP that S` applied twice, with `S → NP VP` and `VP → IntransVerb` at the bottom. This output was the main debugging tool for A.2 and A.4, since it shows which rule is responsible for each structure."));

// ======================= A.4 =======================
add(H1("A.4  Additional structures: (b) yes-no questions and (d) wh-questions"));
add(P("`grammar4` extends `grammar2` with phenomena **(b)** and **(d)**; its first line is `# b d`. Since (b) is implemented, (d) is done with real wh-questions (*what did the president think ?*), not with *I wonder* sentences. The grammar still generates everything from A.2 and A.1."));
add(H2("Why this pair"));
add(bullets([
  "**(d) is built on (b).** A wh-question is a yes-no question with one NP replaced by a gap, plus a wh-phrase in front: *did Sally eat a sandwich ?* becomes *what did Sally eat _ ?*. So the wh-rules reuse all of the yes-no machinery.",
  "**It fits the A.2 design.** The verbs are already split by subcategorization frame. Questions only add a base-form copy of each frame (*did Sally eat*, with the base form *eat*); no existing rule changes.",
  "**No word-level conflicts.** (a) *a*/*an* depends on the first sound of the next word, even across adjectives; (e) agreement splits every NP and VP by number; (f) needs 12 tense/aspect forms. (b) + (d) only add rules.",
  "**The gaps use the standard slash-category technique**, and placing the gaps carefully also blocks the classical ungrammatical questions (islands, that-trace).",
]));

add(H2("(b) Yes-no questions"));
add(P("English forms a yes-no question by **subject–auxiliary inversion**: the auxiliary moves in front of the subject. With a past-tense verb there is no auxiliary, so **do-support** inserts *did* and the verb takes its **base form** (*did Sally **eat***, not *\\*did Sally ate*). A CFG has no features, so the base form needs its own verb classes (`BaseTransVerb`, `BaseIntransVerb`, …) and its own `BASEVP` rules, one per frame, mirroring `VP`."));
add(table(["Rule(s)", "Example", "Why"], [
  ["`PRED → Adj | NP | PresParticiple NP`, `VP → is PRED`", "is lazy", "The three copula rules of A.2 are grouped into one predicate category, so that *is*, *will be* and the inverted *is Sally … ?* all share it."],
  ["`BASEVP → BaseTransVerb NP | BaseIntransVerb | BaseIntransVerb PP | BaseSentCompVerb that S | BasePsychVerb NP that S`", "eat a sandwich", "Bare-infinitive VP with exactly the frames of `VP`. `BaseTransVerb → BaseTransVerb Conj BaseTransVerb` gives *want and eat*."],
  ["`VP → Modal BASEVP`, `VP → Modal be PRED`", "Sally will eat a sandwich .", "Modal declaratives, so that the questions have statements they correspond to."],
  ["`YNQ → did NP BASEVP`", "did Sally eat a sandwich ?", "Do-support."],
  ["`YNQ → Modal NP BASEVP`, `YNQ → Modal NP be PRED`", "will Sally eat a sandwich ? / will Sally be lazy ?", "Inversion with a modal (*will, would, can, should*). *be* exists only after a modal, so *\\*did Sally be lazy* is blocked."],
  ["`YNQ → is NP PRED`", "is Sally eating a sandwich ?", "The copula inverts by itself; no do-support."],
  ["`ROOT → YNQ ?`", "", "Questions end with a question mark."],
], [3300, 2300, 3400]));

add(H2("(d) Wh-questions"));
add(P("A wh-question has a wh-phrase at the front and, for non-subject questions, a **gap** inside the inverted clause where that phrase would normally sit. The gap is passed down the tree with **slash categories**: `X/NP` is an X with exactly one NP missing. Each `X/NP` rule either passes the gap to exactly one child or ends it by leaving the NP out."));
add(table(["Rule(s)", "Example", "Why"], [
  ["`WHQ → WHNP VP`", "who ate the sandwich ?", "**Subject** question: the wh-word is the subject, so there is no inversion and no gap."],
  ["`WHQ → WHNP YNQ/NP`", "who did Sally kiss _ ?", "**Non-subject** question: an inverted yes-no question with one NP gap."],
  ["`WHQ → WhAdverb YNQ`", "where did Sally eat the sandwich ?", "An adverbial wh-word (*where, when, why*) adds no gap, so it is simply placed in front of a complete yes-no question."],
  ["`WHNP → WhPronoun | which Noun`", "who / what / which fine president", "The wh-phrase."],
  ["`YNQ/NP → did NP BASEVP/NP | Modal NP BASEVP/NP | is NP PRED/NP | is NP | Modal NP be`", "did Sally eat _ / is Sally _", "The gap goes into the VP, never into the subject. `is NP` means the gap is the predicate NP (*who is Sally _ ?*)."],
  ["`BASEVP/NP`, `VP/NP` (one rule per frame)", "eat _ / eat the sandwich with _ / work on _ / think _ / think that S/NP / perplex _ that S", "The gap can be the object, sit inside the object's PP, inside a PP after an intransitive verb, be the whole clause of *think*, go into a *that*-clause, or be the object of a psych verb."],
  ["`S/NP → NP VP/NP`", "(that) Sally ate _", "Inside an embedded clause the gap may only be in the VP: a subject gap right after *that* is ungrammatical (the **that-trace** effect)."],
  ["`PRED/NP → PresParticiple | PresParticiple NP/NP`", "eating _", "The object of a progressive participle."],
  ["`NP/NP → NP PP/NP`, `PP/NP → Prep`", "the sandwich with _", "**Preposition stranding**: the gap is the object of a preposition."],
], [3300, 2300, 3400]));
add(P("A derivation of a long-distance question shows how the gap is threaded down to the verb that finally leaves its object out:"));
add(codeBlock(`what did the president think that Sally ate ?
WHQ       → WHNP YNQ/NP
YNQ/NP    → did NP BASEVP/NP
BASEVP/NP → BaseSentCompVerb that S/NP
S/NP      → NP VP/NP
VP/NP     → TransVerb              (the gap ends here: "ate _")`));
add(P("**What the gap placement blocks, by design:**"));
add(table(["Ungrammatical", "Why it cannot be derived"], [
  ["\\* what did Sally eat the sandwich ?", "No gap anywhere: `YNQ/NP` must leave one NP out."],
  ["\\* what did Sally sigh ?", "An intransitive verb has no object to leave out; `BASEVP/NP` has no rule for `BaseIntransVerb` alone."],
  ["\\* who did the president think that ate the sandwich ?", "That-trace: `S/NP` never puts the gap in the subject."],
  ["\\* what did Sally kiss the president and ?", "Coordinate structure constraint: no gap rule goes through `NP Conj NP`."],
  ["\\* what did the president with sigh ?", "Subject island: no gap rule goes into a subject."],
  ["\\* did Sally ate a sandwich ?  /  \\* is Sally eat a sandwich ?", "After *did* only `BASEVP` is allowed, after *is* only `PRED`."],
], [4000, 5000]));
add(P("All of this was checked with the Earley recognizer on 51 sentences (the ten A.2 sentences, the examples of (b) and (d) from the assignment, generalisations of them, and 13 ungrammatical questions): all 51 behave as expected."));

add(H2("Weights and interactions"));
add(P("`ROOT` is weighted 2 + 1 for statements, 1 for *is it true that*, 3 for `YNQ` and 4 for `WHQ`, so that the 50-sentence sample shows the new constructions; inside `WHQ` the object question has the largest weight. The new rules interact with the old ones in the intended way only: the copula predicates, the modal declaratives and the inverted questions share `PRED`, and every frame's base form is reused by *did*, by the modals, and by all the gap rules. The one known bad interaction is inherited from A.2: number agreement is still not modelled, so *is every pickle and the sandwich fine ?* can be generated."));
add(H2("Limitations"));
add(bullets([
  "Every verb frame is written twice (finite and base form), the unavoidable cost of a CFG without features. Adding tense or agreement (phenomena (e) and (f)) would multiply this further.",
  "Clause recursion (`that S` under *think* and *perplex*) occasionally produces very long questions; lowering those two weights would help.",
  "*what did the president think ?* is handled as an NP gap although *what* stands for a clause, which also allows the odd *who did the president think ?*.",
]));
add(H2("Sample output"));
add(P("Sentences from `grammar4.gen` (50 in the file). Yes-no questions:"));
add(code([g4gen[1], g4gen[13], g4gen[6], g4gen[0], g4gen[24], g4gen[22]]));
add(P("Wh-questions (subject, object, long-distance, adverbial, *which*, copula gap):"));
add(code([g4gen[5], g4gen[33], g4gen[35], g4gen[10], g4gen[30], g4gen[19], g4gen[47]]));
add(P("Statements, including the new modal declaratives, are still generated:"));
add(code([g4gen[14], g4gen[3], g4gen[28]]));

// ---------- build ----------
const numbering = {
  config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ...Array.from({ length: numId }, (_, i) => ({
      reference: "numbers" + (i + 1),
      levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
    })),
  ],
};

const doc = new Document({
  creator: "cfg report",
  title: "Assignment 1 Part A: CFG",
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 }, paragraph: { alignment: LEFT, spacing: { line: 276 } } } },
    paragraphStyles: [
      // Defined explicitly: without it Word supplies the user's own Normal style, which on a
      // Hebrew-locale installation is right-to-left and right-aligned.
      { id: "Normal", name: "Normal", quickFormat: true, run: { font: "Calibri", size: 22, rightToLeft: false }, paragraph: { alignment: LEFT, bidirectional: false, spacing: { line: 276 } } },
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", run: { font: "Calibri", size: 40, bold: true, color: "1F3864" }, paragraph: { spacing: { before: 0, after: 240 } } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Calibri", size: 30, bold: true, color: "1F3864" }, paragraph: { spacing: { before: 360, after: 140 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Calibri", size: 25, bold: true, color: "2F5496" }, paragraph: { spacing: { before: 240, after: 100 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Calibri", size: 22, bold: true }, paragraph: { spacing: { before: 160, after: 80 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering,
  sections: [{
    properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("wrote", OUT, buf.length, "bytes");
});
