# X2.10 round 6: steel-man review (D161)

Claude (steel-man subagent), 3 Nov 2026, evening. Covers the post (`web/template.html`) and the runs since round 5. Written without reading this round's critic. No model was run. CPU only.

## Verdict

**The post undersells its two most interesting results and overspends on caveats that don't change a reader's mind.** It can lose about 500 of its 2,587 words. Four facts need fixing first, and one experiment of about an hour would make the post's central claim much stronger.

## What I checked

**Recounted from saved rows:**
- **T line (`lines2/all.jsonl`, `line_score.json`).** 220 calls: 159 writes (40 `add_node`, 62 `link`, 57 `unlink`) and 61 reads. All 220 equal the same-setup tool. 0 lock errors, 0 verify mismatches, 0 head mismatches. Counts as PATH states them. Lockstep 42,133 + 41,676 = 83,809 positions.
- **Plain loop (`control_plainc.jsonl`, `control_plaind.jsonl`).** 3 of 3 right, no first difference, 4,921 + 6,080 + 5,054 = 16,055 tokens. The `plaind` row repeats one of the three questions through plain `model()`, also right. I read how `exam/controls.py` runs both.
- **Map out (`map_out/result.json`).** 131,072 bytes, 0 differ; 7,979 owned tokens right, 0 wrong; closed exactly @223. The table holds a 52,519-byte image, and the run was teacher-forced.
- **Choice (`choice_score.json`).** Every row in the post's table. Arm A has 27 answers and 3 `NOPATH`; arm D is 20 of 20 `NONE`.
- **Mini (`score.json`, `limits_score.json`, `limits_edits.json`, `r2_more_score.json`).** 2,186, 295,414, 2,552 (496 + 960 + 496 + 600), 6,880, 360,976, `FULL` at 256, and 26,516 (12,640 + 2,000 + 500 + 11,376).
- **Real weights on r1.** All 70 edit rows sum to 795,589 with 0 mismatches. `remainder.json` gives 21 of 11,589 gates left. Adding round 5's 421,104 gives 1,216,693.
- **The post's scene.** `nyc_edit` row `nyc:198`, frozen build, lockstep: closes, reopens, and returns to `b4b3c9dba00b20ea`. It holds.
- **Smaller checks.** 0 of 800 unasked closes across three files (not the 100 new wordings, so the post's 900 is 800 checked). 5 Fulton St, 4 125 St, 3 14 St, 21 stops left off the drawing. Wrong map: 0 of 600, of which 594 are refusals or stop lines. `gh` says the repo is private.

**Through a summarising fetch, not read by me in full:** Agrawal's post and qwenFS's README. Theo should read the lines I rely on below.

**Not checked:** the Hacker News counts and quote (no saved source), qwenGPU, the page in a browser. **Not opened:** any sealed data. Journeys was still running, so I have no view on it.

## Fix before publishing

1. **"6,338 machine steps" has no source I can find.** It's hardcoded in `make_ride.py`. Saved rows for this trip say 5,392 on r1 and 4,898 frozen. The text's "about 6,000" should be "about 5,400".
2. **A missed prediction isn't recorded.** L2 predicted the state returns word for word once the edge writes are removed. It returned on 0 of 20. In `nyc-t2:0` the hash ends `a83b19c5cd9df6a3`, not `b4b3c9dba00b20ea`, and `n_edits` stays at 3. `add_node` doesn't change the hash at all, so the digest can't see new stops. Add this to PATH and `AFTER.md`. "So why bother?" says state can be restored word for word: that's true of close and reopen, and untrue of link and unlink. Say so.
3. **The repo is private, and its name contradicts the post.** `subway-in-the-weights` sits beside a section headed "The map isn't in the weights". Rename it and make it public, or every "check it yourself" line is empty.
4. **The chart's labels use `var(--fg)`, which isn't defined.** The 10 and 53 inherit `--on-mark`: white on light grey in light mode.

**Swap the showcase conversation.** The post quotes `nyc-t2:0`. Its sentence is the one that nearly copies a worked turn ("A new W train starts today, with two brand-new stations..."), and its last reply runs out of budget mid-ramble ("Let me re-read the question"). `nyc-t2:1` also ran whole on the real weights, ended by itself, and uses a different wording: "The T line has opened, and it adds two new stations: Foxglove St and Willow Gate." Its last reply is clean. The swap costs nothing and removes the objection. The near-copy wording did no better, either: 4 of 5 linked, against 15 of 15 on the others. That's small, but it's in the post's favour.

## 1. The top sentence, and what he built

**Top of the post:**

> With no training and no tool server, a language model answered New York subway questions and rewrote the map by writing tool calls to a computer compiled into its own layers, and that computer matched a reference on every call I checked. An ordinary tool gets the same answers in milliseconds.

The second sentence is what makes the first credible. Keep them together.

**What did this person actually build?**

> Not the computer: Divyansh Agrawal built that. Theo, with Claude Code writing most of the code, built a small graph database in C that runs on Agrawal's CPU (a 48 KB program), the wiring that lets Qwen read and write it through ordinary tool calls, a fast simulator checked against the real weights, and an exam with predictions written first and misses published. He made a model use a machine exactly, and measured where that holds and where it breaks. He didn't make the model smarter.

## 2. What's undersold

**The plain loop is the biggest thing here, and it gets two sentences.** Taking the model's top pick, with nothing else choosing tokens, Qwen wrote its own call, and the model went on to write `<tool_response>` and the right station itself. That's 16,055 tokens, every one equal to the right stream. Agrawal's post, as summarised to me, says the merged model can't run under plain `generate()` yet, and upstream's README claims that only for its small `rv-tiny`. So this appears to go past what upstream states. Say that, crediting him, once Theo has read his line himself.

Its limits must travel with it, and the post should state the first two right there, not in an FAQ:
- Memory is injected first and stop tokens are off.
- Reads only. **No write has been tested this way, so no hook may join "nothing outside" to "built a line".**
- 3 of 3 has a Wilson lower bound of 44%.
- Qwen's reply afterwards is garbage.

**Writes are undersold on evidence and at risk of being oversold on novelty.**
- **The evidence:** 159 writes in 20 conversations, each read back in a later turn from the model's own state, with no call differing from the reference or the tool. Qwen wrote 1.6% of the tokens. On 2 conversations, the state read from the real weights' heads matched at every call. The post gives only "20" and "19".
- **The novelty:** qwenFS, per its README, already has Qwen writing files and links into a compiled circuit, with a thinner chat loop than this post's driver. So don't imply a first. What's distinct here is traversal over what was written (a new stop reached by `chase`), at 496 stops on a general CPU running C, tested by exam. The post's FAQ mentions qwenFS only as a route to a smaller outside part. A knowledgeable reader will want the comparison stated once.
- **The tool tie covers writes too:** 220 of 220. The post says it only for reads. Say it for writes.

**Also undersold:** the checker catching 8 of 8 flipped bits is there, but 1.2 million real-weight positions on this build isn't. 0 of 60 false calls (Wilson upper bound 6%) is presented as a table, not as the surprise it was.

## 3. What would turn heads

**Hook:**

> I loaded New York's subway into a computer inside an AI model, told the model a new line had opened, and it built the line itself. It takes a minute to do what a tool does in milliseconds, and I published every miss.

Use "inside an AI model", never "in the weights". For LinkedIn, lead with its second sentence: candour is the unusual part there.

**Lead clip: the T line being built on the black map**, about 12 seconds, tool calls typing beside it, from `nyc-t2:1`. It's the one image that shows a write, it needs no explanation, and the map is pretty. Caption: "Qwen's own calls, real weights. 19 of 20 conversations linked it. Positions drawn by the page: the machine has no coordinates." That last clause matters, as the curve is invented.

**Reply-post material, not the lead:** the blackout clip (those were direct calls, not Qwen, so caption it) and the raw text of the model writing its own tool response.

**Avoid:** "first", "no tool", "the model knows the subway", and any pairing of "nothing outside" with the T line.

## 4. Caveats: keep and cut

**These earn their place:** the tool tie; 147 of 200 first and the fix not blind; "the map isn't in the weights"; real weights against simulator; wrong closes and the game; garbage replies without the driver; "I can't name a production system". They're the post's main asset.

**Add three short ones:** the plain loop's limits above; all worked turns are subway turns, in the choice section; state doesn't return after unlink.

**Cut, by section:**

| Section | Cut |
|---|---|
| Intro | "with 704 points and 146 comments" |
| Scene 10 | "Before this, the most I'd closed at once was 12." |
| It got New York right | "That's about 0.3% of the frozen exam: about 40 of the 11,750 circuit gates reached were never compared." Replace with: "On the fix's build, the real weights have now run 1.2 million positions, and 21 of the 11,589 gates reached are uncompared." The old figures are stale |
| New York then broke | The whole paragraph "A later build also treats..." Scene 11 and "What's inside" already say a separate version exists |
| New York then broke | In "After the fix...": the first sentence, and "In its own words... none names a different station." Keep 97 of 100, 84 of 100 with 9 wrong, and the stop-line sentence |
| Its judgment | The Frozen column. The parenthetical "(frozen: 16 conversations ended...)" goes with it |
| Its judgment | Shorten the T-line sentence to "On the T line, 7 of 20 conversations hit a limit before finishing, and one linked the line again after cancelling it." |
| Fair questions | All of "Who cares?", which repeats "So why bother?" |
| Fair questions | "Isn't it a Rube Goldberg machine?" Move the Neural Turing Machines credit into "Isn't this just a tool call?" |
| Fair questions | "Why isn't it all in the model?": keep the qwenFS and read-only map sentences, drop what repeats "What's inside" |

That's about 300 words from the sections and more from tightening. Keep the state digests, the game and the "ask" widget. "So why bother?" needs no cut, as it's the best section.

## 5. What an Anthropic researcher would want

1. **Silent wrong answers as the headline metric.** Machine 0 wrong and 53 refused, against the map's 36 wrong, is really a statement about abstention. A selective-accuracy framing is more interesting to them than "right".
2. **Intervals on small counts.** 20 of 20 is 84-100%, 19 of 20 is 76-99%, 3 of 3 is 44-100%. One line or a footnote will do.
3. **An evidence label on each result:** blind, post hoc or exploratory. The T line and choice are exploratory, with prompts and questions written by the author. The post says this piecemeal, and a small table would replace several sentences.
4. **A symmetric baseline.** The machine got worked turns and the map arm didn't, with thinking off. The post admits it, but they'd want the arm run. There's no Qwen-with-map baseline for writes at all.
5. **Test the monitor claim, or don't lean on it.** "Monitors a model can't quietly edit" is the part they'd care about most, and nothing here tests it. What happens when the model is told to corrupt the machine, forge a `<tool_response>`, or write memory outside the tool? That's a clean, cheap post-launch experiment, and more relevant than any further subway work. Until then, keep it as Agrawal's argument, as the post does.
6. **Review independence.** "Separate reviewer agents" aren't independent humans. Getting one human to run the bundle's walker before launch would be worth more than another AI round.
7. **A reproducer.** One command that rebuilds the merged model from public Qwen plus a recipe, without shipping 18.8 GB, and replays one question. "Answers are checkable" doesn't check that the weights produced them.
8. **Naming the open problem.** Exact and fuzzy parts don't yet share one stream: without the driver, Qwen can't reply. That's the honest research question, and it deserves a sentence as such.

## 6. The next experiment for Wednesday

**The plain loop with a write, registered first in `exam/AFTER.md`.** It's the only available run that joins the post's two best claims into one sentence: *with nothing outside choosing tokens, Qwen wrote to its own graph, and the answer moved.*

- **Arms:** the first 3 closure conversations of r1's seeded draw, turn 1 only, so `closed` is Qwen's own pick and the wording isn't chosen for flattery. On r2, one `add_node` and one `link`, on a wording that doesn't copy a worked turn. Afterwards read the state from the model's heads.
- **Then one attempt at two writes in a row,** as a descriptive row. It tells us whether Qwen survives the machine's tokens at all, which is the open problem above.
- **Cost:** the plain loop ran 16,055 tokens in 1,336 s, about 12 a second on a shared GPU. Closures at about 8,000 tokens are about 11 minutes each, and the `add_node` and `link` about 8 minutes together. Budget about an hour with the × 1.5 rule, under memguard's 32 GiB, one GPU process.
- **My predictions:** Qwen's call right on 3 of 3, since nothing differs before the call. Line right and only that bit set on 3 of 3. `add_node` and `link` right. Second write in a row right: 20%.
- **A failure still gives the post a true sentence:** "Reads work this way; writes don't yet."
- **It's unreviewed on Wednesday,** and should say so.

**Queue change, Theo's or the lead's call.** After journeys, `queue6.sh` runs `lines` (superseded by L2), then gaslight, then `control_zeroed`. Move `control_zeroed` next. At 600 s it's the cheapest high-value run left, and if Qwen invents its own tool response with the chip layers zeroed, that's a striking side-by-side with the plain loop. Then this run, then the query exam. Drop `lines` for tonight.

Sealed New York stays held, as Theo decided.

## Where the best case still fails

- Accuracy gain over a tool is zero, on reads and writes alike, at about a minute a lookup.
- The driver-free result is reads only, on 3 questions, with stop tokens off and Qwen unable to reply.
- Qwen's writes rest on worked turns and my own wordings, and 14 of 30 trick sentences close a station wrongly.
- The fix has had no blind test on a new map.
- qwenFS has a thinner loop and model-driven writes. This work's edge is scope and testing, not priority.
- The best use, monitors, is an argument with no result behind it.
