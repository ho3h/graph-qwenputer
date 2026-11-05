# X2.10 — Graph qwenputer: a compiled graph computer inside Qwen 3.5 (design r2; read "Revision r2" at the end first, it overrides what follows)

Theo, 2026-11-01: "We want a graph qwenputer with the city maps as its indelible proof... We must always strive for
the true graph qwenputer. No shortcuts." He chose option 1: a compiled graph machine first, then the one-pass track.

The critical and steel-man reviews (reviews/) rejected r0 as "qwenputer's store plus a schema" and returned r1 with
required changes. r1.1 meets those changes. The change logs at the end map each one to its place in the text.

## What it is
A graph-native computer compiled into Qwen 3.5's weights, on qwenputer's substrate
(github.com/divagr18/qwenputer, MIT). It extends qwenputer's verified CPU: the graph instructions are macros in the
chosen base's free opcode space (CHIP-8's 5XYN-style space or RV custom opcodes, decided in A0).
- **Phases A–D have no learned weights.** Every weight is computed by the compiler. The machine is exact in bf16, runs
  under stock `transformers`, and answers every limit explicitly.
- **Phase E adds one declared learned port** (see E). The machine and Qwen stay frozen.

### Memory (Gated DeltaNet heads, one-hot address-group keys, exact row overwrites)
- **Nodes** have 12-bit handles (envelope N ≤ 4,096), plus one 16-bit integer property and one 16-bit scratch
  column per node. Programs use the scratch column, so they never overwrite a node's property.
- **Labels (names) map many to one.** A hashed directory (seeded GF(2) hash, linear probing, tombstones, ported from
  qwenputer-RV's store) holds full names up to 16 tokens and verifies the whole name on a hit. Each label chains every
  node that carries it, and lookup reports how many match.
- **Relations** are data: a hashed directory of any names, in any number.
- **Edges** are stored as out-lists and in-lists, each with one 16-bit integer weight. A free list hands out rows,
  and `FULL` comes back when they run out.
- **Neighbour sets for `EXPAND`** are bit rows per (node, indexed relation). They exist only for relations that boot
  data declares as indexed, within the `EXPAND` envelope below.
- **E's tables** (the hop tables and the one-read name table) are part of this memory model from Phase A. Every
  `ADD`, `DEL` and `close` keeps them current, and B1 checks them. They are compiled only if B0 passes.

### Capacity law (estimates now; A computes and verifies the exact law before it freezes)
Rows are 128 per key head.
- **Adjacency and directories** grow linearly. E edges need about E/128 key heads per field.
  - NYC (496 nodes, about 1,761 edges): about 14 key heads for edges, plus directories.
  - CLUTRR graphs are small (tens of nodes).
  - The full envelope (4,096 nodes, 16k edges): about 128 key heads per field.
- **`EXPAND` grows with the square of N.** Per indexed relation it needs about (N/128) × (N/252) key heads:
  - about 8 at N = 496;
  - about 33 at N = 1,024;
  - about 520 at N = 4,096.

  So `EXPAND` has its own envelope: N ≤ 1,024 and at most 4 indexed relations. NYC indexes one relation, the union of
  all moves, for fewest-stop search. Beyond that envelope the library's cursor search runs instead. It is exact and
  just slower.
- **In-degree must stay within bf16's exact range.** Beyond it, `EXPAND` answers `DEGREE`.
- **E's tables are counted too, compiled only if B0 passes.**
  - K copies of the hop table. Keys are hashed (node, relation) pairs read by p parallel probes, and an insert
    beyond the probe depth answers `PROBE`.
  - The one-read name table.
  - The mention register.

  A computes their head counts for NYC, CLUTRR and the envelope.

### The core instruction set
| Group | Instructions |
|---|---|
| Registers | 8 handle registers, 4 integer registers (16-bit, built as byte pairs with carry), a count `C`, a flag `F`, `PC`, a call stack |
| Integers | `LDI`, `ADDI`, `SUB`, `CMP` (sets `F`), `DEC C`; `OVERFLOW` beyond 16 bits |
| Names | `RESOLVE(label [, has-rel filter]) → handle \| AMBIG(k) \| NONE`; `PRINT(handle)` |
| Edges | `FIRST/NEXT(handle, rel, out\|in) → handle, weight \| END` (cursor); `ADD`, `DEL` (`FULL`) |
| Properties | `GETP`, `SETP` (node property), `GETS`, `SETS` (node scratch column) |
| Marks | `MARK`, `TEST`, `CLEAR` (visited bits) |
| Queue | `PUSH`, `POP` |
| Sets | `SCLR(s)`, `SADD(s, h)`, `SHAS(s, h)`, `SOR(s, t)`, `SAND(s, t)`, `SDIFF(s, t)`, `SEMPTY(s)`, `SFIRST(s) → lowest handle`, `EXPAND(s, rel, out\|in) → s′` (one multi-hot DeltaNet read returns the union of the frontier's neighbours, thresholded at > 0 back to bits: one BFS level in one record; `DEGREE` beyond the exact range) |
| Control | `JZ`, `JNZ`, `JF`, `JMP`, `CALL`, `RET`, `RESP` (print a response) |

### The library (BIOS: boot data, not hardware)
- `follow(h, rel, n)`: a loop on `C`. It answers `MULTI(k)` when an out-degree exceeds 1.
- `chase(start, [(rel, n)…])`.
- `neighbours(h, rel)`.
- `path(a, b)`: an `EXPAND` BFS that keeps each level's set. It rebuilds the path backwards: from b, it takes the
  lowest-handle in-neighbour found in the previous level's set. It returns the hop count and the canonical path.
- `close(h)` and `reopen(h)`: for each in-edge (p, r, x) and out-edge (x, r, s) under a relation marked
  splice-through in boot data, add (p, r, s); then delete x's edges; then log the change so it can be reversed
  exactly.
- `cheapest(a, b)`: Dijkstra over the integer weights, run by the cursor (small graphs).

### Control and the bridge
- **Qwen is the control unit.** It writes native tool calls (`<tool_call><function=chase>…`), which the circuit
  captures as Qwen writes them. The circuit runs the program and prints `<tool_response>` itself. Nothing runs on the
  host.
- **Handles keep identity.** Calls and responses carry handles (`@217 Times Sq-42 St`), so identity survives every
  round trip. An ambiguous name is reported, never resolved silently.
- **One instruction word, two ports.** Calls and the future one-pass port write the same fixed-width word: opcode,
  then operands as address groups.
- **Maps load from snapshots.** A map loads from a snapshot of the graph heads, so it is never visible text to Qwen.
  Boot-record prefill is the fallback.

## Generality contract (every gate tests it)
1. **One checkpoint, any graph.** Moving between graphs changes only boot data.
2. **Programs, not hardware.** No circuit exists per hop count, per relation, per question shape or per domain.
3. **Exact or loudly failed.**
   - Every circuit-owned token is checked against the reference, and one mismatch fails.
   - A tool response that Qwen writes itself, because the circuit missed the call, is a failure.
   - Every limit (`FULL`, `AMBIG`, `MULTI`, `NONE`, `DEGREE`, `OVERFLOW`, `COLLIDE`, `PROBE`) has an explicit, tested response.
4. **Post-freeze programs.** After Phase C freezes the weights, the critical reviewer chooses at least three graph
   algorithms that are not in this document. They are written as boot programs only and must run exactly against
   networkx.
5. **Held out, stated honestly.** NYC shaped r0, so it is not held out from design history; from r1 on, no design
   choice uses it.
   - **Never used for design:**
     - CLUTRR kinship (the repo's 2,194 official records, with composition rules loaded as a second graph);
     - a counterfactual NYC (real names, registered rerouting and swapped stations) and an isomorphic relabelled
       copy;
     - the post-freeze programs.
   - **Development** uses random graphs (random names, multi-edge relations, cycles, weights) and the synthetic cities
     c024–c027.

## Baselines (measured in Phase A, before any circuit work)
- **Host-tool ceiling.** Base Qwen with a real host networkx tool, using the same schema and byte-identical responses.
- **Agreement noise floor.** Transcript agreement for that base setup between two attention implementations (eager
  and SDPA), on a decoding path fixed in Phase A. Two greedy runs of one setup always agree, so they cannot give a
  floor.
- **Qwen's spellings.** How Qwen actually spells names inside tool calls, across all graphs, leading-space variants
  included.
- **Software on qwenputer.** The registered queries written in C for qwenputer-RV and counted in its reference
  emulator on the Mac CPU: trace tokens and wall time.
- **Map in the prompt, no chain of thought.** From X2.7, descriptive only.
- **Map as stored text** (qwenputer store put/get), suggested.

## Phases (logged development first, then one frozen gate run per phase; each gate stops on failure)
| Phase | What | Gate (literal) | Machine |
|---|---|---|---|
| A0 | Base and vendoring | Choose main (CHIP-8 + store v1) or experimental/riscv (RV + hashed store) as the base, by extensibility and merged size. Vendor a pinned copy with its licence into `X2.10/vendor/`. | Mac CPU |
| A | Reference, library, instruction word, capacity law, baselines | **A1:** on random graphs (seeds 0–99), c024–c027, counterfactual and real NYC and CLUTRR, every library routine equals networkx 100%, every limit gives its explicit response, and `path` equals the canonical BFS. **A2:** the reference spells every call and response exactly as Qwen's tokenizer does, including every spelling variant measured in the baselines. **A3:** `EXPAND` is exact in a direct DeltaNet-head test over its whole envelope (N ≤ 1,024, in-degree up to the `DEGREE` bound). **A4 (cost predictions):** on NYC-scale graphs, `path` by `EXPAND` uses ≤ 1/10 of the RV C BFS's trace tokens, and `chase` uses ≤ 1/5 of the RV C chase's. If A4 fails, the claim that `EXPAND` has no CPU counterpart is removed from every description, and the machine stands on its other claims. | Mac CPU, mini |
| B0 | One-pass feasibility (before B) | A compiled two-hop pipeline on real Qwen 3.5 weights, through the HF modules in bf16 on MPS, over ≥ 10,000 real-text positions, with a dedicated chip layer inserted mid-stack. **B0a:** text KL within 1.5× the noise floor with the carried dims live. **B0b:** the read is exact, including ballast re-injected and then cleared exactly; the short convolution using only the current token; a constant carried at the address's scale; no write or decay in the graph-table heads at text positions; margins held over the real RMS spread (outliers included); the dims counted in the size target. **B0b2:** read, then next key from an MLP, then a second read with `C`, then exact mid-stack writes from chip tokens, an exact mid-stack write at a mention's text position keyed by mention order, and a snapshot restore. **B0c (learned, declared):** a port of ≤ 2M parameters, trained on synthetic graphs only, supervised by instruction words generated from templates (Phase D does not exist yet), with Qwen and the machine frozen, chooses the mention, relation and count from Qwen's layers. It must be ≥ 90% right on held-out synthetic cities in held-out phrasings (X2.9's prior: 5–25%). A B0 pass means "E can be built". Any failure drops E, and A–D are described as an exact graph computer in the weights. | MPS (calendar) |
| B | Circuit in qwenputer's IR | **B1:** the IR evaluator equals the reference token for token on ≥ 1,000,000 trace tokens: random graphs, every instruction and limit, E's tables kept current by every edit, programs not in the library, ≥ 100k text tokens between calls, snapshot restore. Every bf16 rounding is checked; 0 mismatches. | mini, Mac CPU |
| C0 | Size and MPS pilot | A graph-only build on 0.8B, then 4B. Disk size and resident MPS memory against ≤ 20 GiB at gate decoding. MPS exactness on ≥ 10,000 circuit-owned positions. Declare the D decoding path; if B0 passed, it must be one in which chip tokens reach the mid-stack chip layers. If that path differs from Phase A's, C0 re-measures the agreement floor on it. | MPS |
| C | Merged checkpoint | **C1:** teacher-forced, 0 wrong of all circuit-owned positions on random sessions (seeds 0–19). **C2:** text KL within 1.5× the noise floor. If B0 passed, E's port and layers are merged inert, and C1–C2 hold with them present. | MPS |
| D | Qwen drives it | **D1 / D1m** (chained calls / one `chase` call): 200 two-leg chases each on NYC, counterfactual NYC and the relabelled city, drawn from registered seeds. Accuracy ≥ the host-tool ceiling − 2 points, and per-question transcript agreement with the host tool ≥ the noise floor − 1 point. **D2m (machine, direct calls):** 20 registered closures, each scored on all 600 chase questions: 100% of affected answers change to the re-solved answer, 100% of unaffected answers are byte-identical, and reopening restores all 600. **D2q (Qwen end to end):** 5 closures × 100 sampled questions (registered seeds), accuracy ≥ the host-tool ceiling on the same items − 2 points. **D3:** CLUTRR's official records with rules as data, accuracy ≥ the host-tool ceiling on the same items − 2 points. **D4m (machine, direct calls):** 500 registered pairs per graph: `path` equals the canonical BFS 100% (hop count and path). **D4q (Qwen end to end):** 100 sampled pairs per graph, accuracy ≥ the host-tool ceiling − 2 points. **D5:** each post-freeze program on 200 registered instances, exact 100%. **Controls:** graph state zeroed, the other city loaded, and no machine, each ≤ 5% on D1 for the counterfactual and relabelled cities. On real NYC they are reported descriptively, because Qwen knows the subway from pretraining. **Cost:** trace tokens and wall time per question against the RV baseline (A4's predictions). | MPS |
| E | One pass (registered after D, only if B0 passed) | Draft, unfrozen. The map is snapshot-loaded, with a collision-free one-read name table built alongside it, since a probing search cannot run in one pass. A name added at runtime that would collide in it gets an explicit `COLLIDE` response, checked in B1. Front chip layers resolve the prompt's mentions exactly. The B0c port chooses mention, relation and count. Mid-stack hop tables over K layers hop exactly. On held-out multi-hop questions, the answer must be correct with zero trace tokens and zero reasoning tokens, above map-in-context without CoT and above the facts fine-tuned into weights. After B0c's template training, D's transcripts become the port's further curriculum. | MPS |

## Novelty, stated plainly
- **Already in qwenputer:**
  - exact RAM in DeltaNet state;
  - tool-call capture;
  - chip records, snapshots and hashed directories;
  - macros that loop and branch;
  - a general RISC-V core that could run a C graph library.
- **New, and measured against that core:**
  - a graph-native instruction set whose set-at-a-time `EXPAND` has no CPU counterpart (A3, A4; the claim is
    withdrawn if A4 fails);
  - graph algorithms as data, tested by post-freeze programs;
  - exact, specific and reversible edits across every answer;
  - one checkpoint across transit, kinship rules and counterfactual maps.
- **The claim no database can make** is Phase E. It is designed in from Phase A (the shared word, E's tables, B0).
  It is dropped honestly if any part of B0 fails.

## Rules carried over
- **Development and gates.** Logged development (bugs fixed and recorded) stays separate from the single frozen gate
  run per phase. Each gate gets one attempt plus one documented revision, then stops and goes to Theo.
- **Budgets.** Budgets come from dev timings × 1.5, are recorded before the freeze, and are never raised.
- **Reviews.** Each round gets a critical and a steel-man review.
- **Qwenputer code.** It stays read-only in Theo's clone; we work on a vendored pinned copy, and his local qwenputer
  setup and its processes are not touched.
- **Machines.** Check the GPU calendar before any MPS work. Pile CPU work (IR runs, emulator baselines) onto the mini.
- **Downloads.** None without asking. CLUTRR is in the repo. MQuAKE (multi-hop knowledge editing, with published
  baselines) would need a download: a decision for Theo.

## Change log r0 → r1 (critical 1–11, steel-man required items)
Composable primitives with programs; multi-edge semantics; handles, `AMBIG` and hashed full names; Phase E decided
in; novelty tests; host-tool ceiling; precise gates; honest held-out rule; feasibility steps; capacity as a law with
snapshots; development separate from gates.

## Change log r1 → r1.1
| Required change | Where r1.1 meets it |
|---|---|
| Capacity law with numbers, including `EXPAND`'s quadratic term; only declared relations indexed (critical 1; steel-man R3) | Capacity law; the `EXPAND` envelope; `DEGREE` |
| Integer registers and arithmetic, and integer edge and node properties (critical 2; steel-man R6) | Registers, Integers, Properties; `cheapest` |
| Ceiling, agreement noise floor and spellings measured before circuit work (critical 3) | Baselines; D1's bar against the noise floor |
| Literal D2–D5, controls and cost predictions (critical 4; steel-man R7) | Phase D; A4 with its failure meaning |
| B0 rescoped: two-hop pipeline, the five conditions, B0c, E dropped on any failure (critical 5; steel-man R1, R5) | B0a, B0b, B0b2, B0c |
| E's conflicts with the decoding path and directory resolved (critical 6) | C0's decoding-path rule; E's one-read name table |
| E's tables in the A–D memory model, kept by every edit and checked in B1 (steel-man R4) | Memory; B1 |
| The full Sets and count instructions, and how `path` rebuilds the path (steel-man R2) | Instruction set; library |
| No named examples in the post-freeze contract (both) | Contract 4: the critic chooses them |
| MQuAKE as a download decision for Theo (steel-man, suggested) | Rules carried over |
| 16-bit integers, a per-node scratch column, `OVERFLOW` (critical r1.1-1) | Memory; Registers; Integers; Properties |
| An agreement floor across two attention implementations, on a decoding path fixed in A (critical r1.1-2) | Baselines |
| D2 and D4 split into machine-level (100%) and sampled end-to-end (ceiling − 2) parts (critical r1.1-3) | D2m, D2q, D4m, D4q |
| A loud `COLLIDE` for runtime names in E's table, checked in B1 (critical r1.1-4) | E; contract 3 |
| A mid-stack write at text positions in B0b2; the no-write rule limited to graph-table heads (steel-man r1.1-1) | B0b, B0b2 |
| `SOR`, `SAND`, and in/out on `EXPAND` (steel-man r1.1-2) | Sets |
| E's tables in the capacity law: hashed hop tables with probes, `PROBE` (steel-man r1.1-3) | Capacity law; contract 3 |
| B0c supervised by template instruction words; held-out phrasings (steel-man r1.1-4) | B0c |
| `OVERFLOW` (steel-man r1.1-5) | Integers |
| Control bars only on the counterfactual and relabelled cities (steel-man r1.1-6) | D controls |

## Revision r2 (Theo, 2026-11-01, after development round 1)
Both reviews of round 1 (`reviews/dev-round1-*.md`) found that Phase E as designed has missed. Theo chose: two cheap
tests and the C library first, then the graph hardware, under three conditions. His words on the choice: "Yes I like
this. Proceed."

**Phase E as specified is dropped.** No frozen gate fired, but an unfrozen gate is not a loophole. Outward descriptions
use "an exact graph computer in the weights". Anything that revives a zero-token mode needs Theo's decision and its own
registered name, and cannot inherit E's claim. E's tables, `COLLIDE`, `PROBE` and the shared instruction word leave
Phase A and B1 for now; the review in step 4 may bring back what the tests justify.

**Order.**
1. **CI, compact instruction** (`ci/REGISTRATION.md`). Can Qwen write a one-line instruction with no reasoning, on a pool
   written blind to the port's failures? 90% bar unchanged. A pass is a smaller claim under its own name, never "one pass".
2. **WB, write-back** (`wb/REGISTRATION.md`). Can a machine hop's answer, put in at layer 16 of 32, be used by Qwen's
   own next hop inside one token? A host-side spike, with no compiled chip.
3. **The C library through Qwen on the RISC-V core** (`rvc/`). The first exact machine for the city proof, behind the
   same SPEC and at D's existing bars. It runs alongside 1 and 2. Reported as what it is: qwenputer plus a program, and
   general because it runs any graph program.
4. **Design review of the graph hardware,** using the results of 1–3. The hardware is still built; this review decides
   its form.
5. **The graph hardware.** Same library and interface, so it replaces no work done in 3.

**The three conditions on the hardware (Theo accepted these).**
1. **The reason is capacity and being graph-native, not token savings.** A4's bars stay as registered, and if the frozen
   run misses them the `EXPAND` cost claim is withdrawn as already written. Nothing redefines A4.
2. **It has its own test.** It must match the C library byte for byte on everything both can run, and also run, exactly,
   a registered graph that the software build cannot hold. That graph is named and registered before the hardware is
   built.
3. **Its design is reviewed after steps 1–3,** and may change. The critic's position was "build only on evidence". Theo
   decided to build it because of what the machine should be. That is recorded here as his decision, not as something the
   data required.

**Also before step 5:** a written capacity law, and a Phase D budget in tokens and hours from measured rates (D2m alone is
about 37.4M tokens at about 3,118 per question).

### Theo's steers after r2 (2026-11-01)
- **Query tool:** lean towards one strong query tool, trying options before settling. Replacing the ten SPEC functions is not decided; QW's result informs it.
- **Reasoning:** try it on failures and as the default, to find the tradeoffs. Both are QW arms. It is no longer banned as a purity condition.
- **Value:** matching an external tool may be hard, and this is a proof of concept regardless, but it should show at least one major finding or metric that demonstrates value. Which one is open.
- **Speed:** a clean rate with the GPU alone is still unmeasured; the 2-minute figure is arithmetic from a shared Mac.
- **Headline metric (Theo agreed):** (1) instant, exact edits lead, with a measured comparison against a weight-editing method on our own items, not a quoted figure; (2) answers Qwen can't know is the demo, against Qwen alone and the map pasted in the prompt; (3) nothing outside the model is the framing. The weight-editing comparison is unregistered and needs its own registration.
- **Executor and run ceiling (Theo, 2026-11-01):** "yes executor we must use for proof of concept, testing", with "small comparison to qwen periodically" to confirm it holds for larger work, and "anything above 4 hours is just unrealistic". So tests and proof runs may use a compiled executor, checked against the stock weights. No single run may be planned above 4 hours. Results state which way each ran. See `exec/REGISTRATION.md`.
- **Answer mode (Theo, 2026-11-02, on T1):** a setting with two modes. **Pass to Qwen is the default:** Qwen reads the machine's line and gives the response. **Print** shows the machine's line as the answer, "useful for speed/if the user wants". The machine and checkpoint are the same in both; only what happens after the machine's line differs. Each mode is scored and named separately, so print's exactness is never claimed for pass to Qwen.
- **Theo's answers on `d/PLAN.md` (2026-11-02):** T2, decide the size of the read-back test after the one-tool run. T3, left to Claude: the same-setup tool carries the bar, and the ten-tool figure is reported beside it. T4, the newer firmware, "so long as we don't compromise our vision". T5, CLUTRR is no longer required: "After we crack NYC we should create like 5-10 random different challenges to find the limit of what this is capable of". T6, strict marking for now, and he wants to read the full answers himself later, so every test saves them whole. T7 and the total test time wait: "let's get as optimized as humanly possible then evaluate time estimates". Speed work starts now. T8 waits on a clearer explanation and the fresh test.
- **Start name, T8 (Theo, 2026-11-02):** build in the strict cleaner, chosen from five tried (`t8/RESULTS.md`). On `NONE` only, remove trailing punctuation and the graph's own noun for a node, then require an exact match, and state the reading in the response. Anything else stays a loud `NONE`.
- **Limit lines (Theo, 2026-11-02):** the machine prints `Stopped early on leg i: ... The journey did not finish.` in place of today's `END`, `MULTI` and `NOCHANGE` lines (`lines/REGISTRATION.md`, W1). Roll into the final build with normal tokens and the strict cleaner.
- **Launch item (Theo, 2026-11-02):** for Wednesday, "make edits" means Qwen makes the edit itself, "showing changes to the internal state". The weight-editing comparison follows after launch.
- **Standard build (Theo, 2026-11-02):** "Edit capable feels like the standard moving forwards." `writes.elf`, with `closed` and `reopened` fields on `chase` and worked turns in the prompt, is the build to freeze and carries the exams. The exams therefore measure that prompt and call shape.

**Tonight's decisions (Theo, 2 Nov evening: "Go for it. Our goal is to achieve as much as possible tonight, so don't wait on me for decisions"), made by Claude under that delegation, listed with reasons in `exam/REGISTRATION.md`:** T7's claim is "executor, sampled on the real weights", stated per result; the uncompared circuit gets a stock window on the exam's own calls and the remainder is named; the 85 exit units are accepted as a bridge fix and disclosed; a gate rule rejects the 250 reserved ids; noun and limit lines come from the frozen loader, with data files unchanged; flow savings aren't adopted; transcript agreement is reported with its bar UNRUN. Scope tonight: real New York only.
