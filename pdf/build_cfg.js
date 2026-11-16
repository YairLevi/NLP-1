// Builds pdf/cfg.docx (the Part A report) with docx-js.
//
// Usage (from a folder where `npm install docx` was run):
//   node build_cfg.js <output.docx> <repo root>
// Sample sentences and trees are read from A.1/, A.2/, A.3/ and A.4/ in the repo.
// cfg.pdf is then exported from the docx with Word (File > Save As > PDF).
//
// Style: plain (one font, no colours), short, and about half of the sentences
// start in lowercase on purpose (seeded, so the output is reproducible).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, AlignmentType, LevelFormat,
} = require("docx");

const OUT = process.argv[2];
const REPO = process.argv[3];
const read = (p) => fs.readFileSync(path.join(REPO, p), "utf8");
const LEFT = AlignmentType.LEFT;

// ---------- seeded "roughness": lowercase the start of about half the sentences ----------
let seed = 7;
const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
const KEEP = new Set(["I", "Sally", "English", "Python", "README", "NP", "VP", "PP", "CFG", "CFGs", "A.0", "A.1", "A.2", "A.3", "A.4", "P(NP", "P(adjective)", "Q1", "Q2", "Q3", "Q4"]);
function rough(text) {
  if (!text) return text;
  const parts = text.split(/(?<=[.!?:])\s+(?=[A-Z])/);
  return parts.map((s, i) => {
    const w = s.split(/\s/)[0].replace(/[*`(]+$/, "");
    if (KEEP.has(w) || /^[A-Z][A-Z0-9/.]*$/.test(w) || /^[`*(]/.test(s)) return s;
    if (i === 0 && rnd() < 0.5) return s[0].toLowerCase() + s.slice(1);
    if (i > 0 && rnd() < 0.5) return s[0].toLowerCase() + s.slice(1);
    return s;
  }).join(" ");
}

// ---------- inline markup: `code`, **bold**, *italic*; "\*" is a literal asterisk ----------
function runs(text, base = {}) {
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

const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, alignment: LEFT, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, alignment: LEFT, children: [new TextRun(t)] });
const P = (t) => new Paragraph({ children: runs(rough(t)), alignment: LEFT, spacing: { after: 120 } });
const Q = (t) => new Paragraph({ children: runs(t, { italics: true }), alignment: LEFT, spacing: { after: 100 } });
const bullets = (items) => items.map((t) => new Paragraph({
  children: runs(rough(t)), alignment: LEFT, numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 },
}));
const code = (lines) => lines.map((l, i) => new Paragraph({
  alignment: LEFT,
  children: [new TextRun({ text: l.replace(/\t/g, "    "), font: "Consolas", size: 18 })],
  spacing: { before: 0, after: i === lines.length - 1 ? 140 : 0, line: 240 },
  indent: { left: 360 },
}));
const codeBlock = (text) => code(text.replace(/\n$/, "").split("\n"));

function table(header, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (cells, head) => new TableRow({
    tableHeader: head,
    children: cells.map((c, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      margins: { top: 40, bottom: 40, left: 80, right: 80 },
      children: [new Paragraph({ children: runs(head ? c : rough(c), head ? { bold: true } : {}), alignment: LEFT, spacing: { after: 0 } })],
    })),
  });
  return [new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, rows: [mk(header, true), ...rows.map((r) => mk(r, false))] }),
    new Paragraph({ spacing: { after: 100 }, children: [] })];
}

// ---------- sample data from the repo ----------
const g1gen = read("A.1/grammar1.gen").trim().split("\n");
const g2gen = read("A.2/grammar2.gen").trim().split("\n");
const g4gen = read("A.4/grammar4.gen").trim().split("\n");
const b3trees = read("A.3/b3.gen").trim().split(/\n(?=\(ROOT)/);

const children = [];
const add = (...xs) => xs.flat().forEach((x) => children.push(x));

add(new Paragraph({ heading: HeadingLevel.TITLE, alignment: LEFT, children: [new TextRun("Assignment 1, Part A: CFG report")] }));
add(P("Answers to the discussion items of part A. a star (\\*) marks an ungrammatical sentence. the probability of a rule is its weight divided by the total weight of the rules with the same left-hand side."));

// ======================= A.0 =======================
add(H1("A.0  the -n switch"));
add(P("`generate.py` keeps the grammar as a dictionary from each left-hand side to its list of (right-hand side, weight) pairs. `gen(symbol)` returns a symbol that has no rule (a terminal) as is, otherwise it picks an expansion at random by weight and generates each symbol in it. I replaced the `sys.argv` handling with `argparse`: the grammar file is a positional argument and `-n` is an optional integer with default 1, so the old call still prints one sentence. the main loop runs `n` times and prints one sentence per line."));
add(codeBlock(`parser.add_argument("grammar")
parser.add_argument("-n", type=int, default=1)
parser.add_argument("-t", action="store_true")   # A.3
for i in range(args.n):
    print(pcfg.random_sent())`));

// ======================= A.1 =======================
add(H1("A.1  weights"));
add(H2("1. why so many long sentences?"));
add(P("The rule is `NP → NP PP`. it is recursive, and through `PP → Prep NP` every use of it turns one NP into two. both NP rules have weight 1, so an NP ends half of the time and doubles half of the time: on average each NP makes exactly one new NP. this is a critical branching process. it ends with probability 1, but the expected number of NPs is unbounded, so the length distribution has a very heavy tail. in 20,000 sentences from the original grammar the median length was 20 tokens, the mean about 276, the longest over 30,000 tokens, and 354 generations (1.8%) crashed on Python's recursion limit."));
add(P("The special thing about the rule is that it is recursive and branching at the same time, and that the grammar is context free: the choice of `NP → NP PP` does not know how long the sentence already is, so it is just as likely deep inside a long sentence as at the start."));

add(H2("2. why are multiple adjectives rare?"));
add(P("`Noun` has six rules with equal weight and only one of them, `Noun → Adj Noun`, adds an adjective. the other five end the noun. so a noun gets one adjective with probability 1/6 and two or more with probability (1/6)² ≈ 3%. with two or three nouns per sentence, a chain like *the fine perplexed pickle* is rare."));

add(H2("3. which numbers to change"));
add(P("Two weights, both in `grammar1` with a comment next to them:"));
add(table(["rule", "old", "new", "effect"], [
  ["`NP → Det Noun`", "1", "3", "P(`NP → NP PP`) goes from 1/2 to 1/4, so an NP makes 0.5 new NPs on average instead of 1. the recursion dies out fast and sentences get short."],
  ["`Noun → Adj Noun`", "1", "3", "P(adjective) goes from 1/6 to 3/8 and P(two or more) from 3% to 14%. adjective chains become common."],
], [2000, 600, 600, 5800]));
add(P("The lesson: a recursive rule is controlled by its weight relative to the non-recursive rules of the same left-hand side. that ratio decides whether the expected number of new copies is below or above 1. verification on 20,000 sentences from each grammar:"));
add(table(["", "original", "grammar1"], [
  ["median / mean length (tokens)", "20 / 276", "11 / 13"],
  ["longest sentence", "30,500", "115"],
  ["recursion crashes", "354", "0"],
  ["mean number of PPs per sentence", "74", "1.0"],
  ["P(a noun has an adjective)", "1/6", "3/8"],
], [4200, 2000, 2000]));
add(P("Some sentences from `grammar1.gen`:"));
add(code(g1gen.slice(2, 5)));

add(H2("4. other numeric adjustments"));
add(P("Equal weights are not how real text looks, so the idea is to move the weights toward real frequencies. I tried the following on a copy of `grammar1`:"));
add(bullets([
  "Most sentences are statements, not questions or exclamations, so `ROOT → S .` got weight 8 against 1 and 1.",
  "With equal weights the output is full of *every* (*every delicious fine sandwich on every pickled floor kissed every president*). *the* got 5, *a* 3, *every* 1.",
  "Same for prepositions: *with*, *on*, *in* 3 each, *under* 1.",
  "*pickled* is a rare adjective, so it got 1 and *fine* / *delicious* got 3. repeated adjectives become less likely too.",
  "Nouns and verbs share one class for subject and object, so weights can only tilt toward words that are fine in both roles (*president* 3, *floor* 1, *ate* 3, *pickled* 1).",
  "`NP → NP PP` lowered to 0.5 to remove most stacked PPs.",
]));
add(P("Sample output with these weights:"));
add(code([
  "every fine perplexed sandwich wanted a chief of staff .",
  "the perplexed president wanted the president .",
  "a pickle wanted a sandwich .",
  "the president kissed the chief of staff .",
  "every floor ate a president .",
  "the president in every fine sandwich wanted the pickled perplexed delicious president .",
]));
add(P("The sentences are shorter and read better, but weights can only shift frequencies, they cannot forbid anything. *every floor ate a president* is still produced because the verb does not know its subject. that needs structural changes (for example animate and inanimate noun classes), not numbers. the submitted `grammar1` has only the two changes of question 3."));

// ======================= A.2 =======================
add(H1("A.2  extending the grammar"));
add(P("`grammar2` adds sentences (1)–(10) and similar ones while keeping the subcategorization frames of the verbs. the main design decision: one verb class per frame (`TransVerb`, `IntransVerb`, `SentCompVerb`, `PsychVerb`), so every VP rule says exactly which arguments its verb takes. this is what blocks *\\*the president sighed a pickle*. single function words (*that*, *is*, *very*, *it*) are written directly in the rules, like the original `is it true that S ?`; a class exists only for a word set with several members (`Conj`)."));
add(table(["sentence", "rule(s)", "why"], [
  ["(1) Sally ate …", "`NP → ProperNoun`", "a proper noun is an NP without a determiner."],
  ["(2) Sally and the president wanted and ate …", "`NP → NP Conj NP`, `TransVerb → TransVerb Conj TransVerb`", "coordination. both rules are recursive. only transitive verbs are coordinated, so both share the one object."],
  ["(3) … sighed", "`VP → IntransVerb`", "no object. a separate class is what blocks *\\*sighed a pickle*."],
  ["(7) … worked on every proposal on the desk", "`VP → IntransVerb PP`", "intransitive verb plus a PP. *on the desk* attaches through the old `NP → NP PP`."],
  ["(4), (10) … thought that S", "`VP → SentCompVerb that S`", "the verb takes a clause, not an NP. the embedded S has its own full VP, so *\\*thought that a sandwich sighed a pickle* is impossible."],
  ["(5) it perplexed the president that S", "`NP → it`, `VP → PsychVerb NP that S`", "object-experiencer psych verb: object plus a *that* clause. *it* is an expletive subject."],
  ["(6) the very very very perplexed president", "`Adj → very Adj`", "recursive, so stacking is free."],
  ["(8) is lazy, (10) is a sandwich", "`VP → is Adj`, `VP → is NP`", "copula."],
  ["(9) is eating a sandwich", "`VP → is PresParticiple NP`", "progressive; the object is required since *eating* is transitive."],
], [2500, 2800, 3700]));
add(P("Words added: *Sally, and, sighed, worked, thought, perplexed, eating, lazy, desk, proposal*. `NP → Det Noun` got weight 6 and `NP → NP Conj NP` 0.5, since with two recursive NP rules the non-recursive one needs more weight (same reason as A.1)."));
add(P("I checked the grammar with a small Earley recognizer (a sentence can be parsed iff it can be generated): all ten sentences are generated, and these are not:"));
add(code(["* the president thought that a sandwich sighed a pickle .", "* the president sighed a pickle .", "* the president ate ."]));

add(H2("the bad interaction between (2) and (8)/(9)"));
add(P("Sentence (2) adds coordination of NPs and (8)/(9) add the copula *is*. *is* needs a singular subject, but *Sally and the president* is plural and needs *are*. the VP is generated independently of the subject, so the grammar produces"));
add(code(["* Sally and the president is lazy .", "* Sally and the president is eating a sandwich ."]));
add(P("as if *is* referred to the pair. the past tense verbs do not have this problem because English past tense does not mark number. a CFG can fix it only by putting the number into the category: `NP_sg` / `NP_pl` (a coordination is always plural), `VP_sg` / `VP_pl`, and `S → NP_sg VP_sg | NP_pl VP_pl`. this doubles the NP and VP rules, and it was not required here."));
add(P("Sample from `grammar2.gen`:"));
add(code([g2gen[0], g2gen[4], g2gen[10], g2gen[18], g2gen[13]]));

// ======================= A.3 =======================
add(H1("A.3  the -t switch"));
add(P("`gen_tree(symbol)` is the same recursion as `gen` but returns a tree: a terminal stays a string and a nonterminal becomes `(symbol, [children])`. `format_tree` prints it in bracket form; a node whose children are all terminals goes on one line, otherwise each child goes on its own line under the first one. `-t` is a `store_true` flag and works together with `-n`. one of the five trees in `b3.gen`:"));
add(codeBlock(b3trees[2]));

// ======================= A.4 =======================
add(H1("A.4  (b) yes-no questions and (d) wh-questions"));
add(P("First line of `grammar4` is `# b d`. I chose this pair because (d) is built on (b): a wh-question is a yes-no question with one NP replaced by a gap plus a wh-word in front. *did Sally eat a sandwich ?* becomes *what did Sally eat _ ?*. both only add rules on top of the A.2 verb frames, nothing existing changes."));

add(H2("(b) yes-no questions"));
add(P("English puts the auxiliary in front of the subject. with a past tense verb there is no auxiliary, so *did* is inserted and the verb goes to its base form (*did Sally eat*, not *\\*did Sally ate*). a CFG has no features, so the base form needs its own classes (`BaseTransVerb` …) and its own `BASEVP` rules, one per frame, mirroring `VP`. the copula rules of A.2 were grouped into `PRED → Adj | NP | PresParticiple NP` so that *is*, *will be* and the inverted *is Sally … ?* share them."));
add(table(["rule", "example"], [
  ["`YNQ → did NP BASEVP`", "did Sally eat a sandwich ?"],
  ["`YNQ → Modal NP BASEVP`", "will Sally eat a sandwich ?"],
  ["`YNQ → Modal NP be PRED`", "will Sally be lazy ?"],
  ["`YNQ → is NP PRED`", "is Sally eating a sandwich ?"],
  ["`VP → Modal BASEVP`, `VP → Modal be PRED`", "Sally will eat a sandwich . (the matching statements)"],
], [4200, 4800]));
add(P("*be* exists only after a modal, so *\\*did Sally be lazy* is blocked; after *did* only `BASEVP` is allowed, so *\\*did Sally ate* is blocked."));

add(H2("(d) wh-questions"));
add(P("The gap is passed down with slash categories: `X/NP` is an X with one NP missing. each `X/NP` rule passes the gap to exactly one child or ends it by leaving the NP out."));
add(table(["rule", "example", "note"], [
  ["`WHQ → WHNP VP`", "who ate the sandwich ?", "subject question: no inversion, no gap."],
  ["`WHQ → WHNP YNQ/NP`", "who did Sally kiss _ ?", "non-subject question: inverted clause with a gap."],
  ["`WHQ → WhAdverb YNQ`", "where did Sally eat the sandwich ?", "*where / when / why* add no gap."],
  ["`WHNP → WhPronoun | which Noun`", "who, what, which president", ""],
  ["`YNQ/NP → did NP BASEVP/NP | is NP PRED/NP | is NP | …`", "did Sally eat _ / who is Sally _", "the gap never goes into the subject."],
  ["`BASEVP/NP`, `VP/NP` (one per frame)", "eat _ / think _ / think that S/NP / perplex _ that S", "object, PP object, whole clause, inside a *that* clause."],
  ["`S/NP → NP VP/NP`", "(that) Sally ate _", "only in the VP: no subject gap after *that* (that-trace)."],
  ["`NP/NP → NP PP/NP`, `PP/NP → Prep`", "the sandwich with _", "preposition stranding."],
], [3400, 2800, 2800]));
add(P("Derivation of a long-distance question:"));
add(codeBlock(`what did the president think that Sally ate ?
WHQ → WHNP YNQ/NP → did NP BASEVP/NP → BaseSentCompVerb that S/NP → NP VP/NP → TransVerb _`));
add(P("What the gap placement blocks: *\\*what did Sally eat the sandwich ?* (no gap), *\\*what did Sally sigh ?* (no object to leave out), *\\*who did the president think that ate the sandwich ?* (that-trace), *\\*what did Sally kiss the president and ?* (no gap into a coordination), *\\*what did the president with sigh ?* (no gap into a subject). all of this was checked with the Earley recognizer on 51 sentences, 13 of them ungrammatical."));
add(P("Weights: `ROOT` gives 3 to `YNQ` and 4 to `WHQ` so the 50 samples show the new structures. limitations: every verb frame is written twice (finite and base), which is the price of a CFG without features; the agreement problem of A.2 is still there (*is every pickle and the sandwich fine ?*); and *what did the president think ?* is treated as an NP gap although *what* stands for a clause."));
add(P("Sample from `grammar4.gen`:"));
add(code([g4gen[1], g4gen[13], g4gen[0], g4gen[5], g4gen[33], g4gen[35], g4gen[10], g4gen[19], g4gen[47], g4gen[14]]));

// ---------- build ----------
const doc = new Document({
  title: "Assignment 1 Part A: CFG",
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 }, paragraph: { alignment: LEFT, spacing: { line: 264 } } } },
    paragraphStyles: [
      // Explicit Normal: otherwise Word takes the user's Normal, which is right-to-left here.
      { id: "Normal", name: "Normal", quickFormat: true, run: { font: "Calibri", size: 22, rightToLeft: false }, paragraph: { alignment: LEFT, bidirectional: false, spacing: { line: 264 } } },
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", run: { font: "Calibri", size: 36, bold: true }, paragraph: { alignment: LEFT, bidirectional: false, spacing: { before: 0, after: 200 } } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Calibri", size: 28, bold: true }, paragraph: { alignment: LEFT, bidirectional: false, spacing: { before: 320, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Calibri", size: 23, bold: true }, paragraph: { alignment: LEFT, bidirectional: false, spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{ properties: { page: { margin: { top: 1300, bottom: 1300, left: 1300, right: 1300 } } }, children }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, buf.length, "bytes"); });
