# Round 18, the one revision: steel-man review of the map arm's result

10 Nov. I read `web/template.html` whole, `release/README.md`, `release/model/README.md`, `release/launch-posts.md`, the round 18 sections of `exam/AFTER.md`, the round 18 bullet of `PATH.md`, `exam/think.py`, `exam/score_think.py`, `web/chart.py`, my pre-run review, and Qwen's own model card in `~/Models/x210/Qwen3.5-4B/README.md`. I copied `think2/P.jsonl` and `P.log` to my scratch folder and worked only on the copies. I ran the registered scorer on the copy, and plain Python over saved rows. I loaded no model, wrote nothing in `think2/`, and touched no process. Arm A is still running, and everything that depends on arm A is marked as held.

The reader I am speaking for is an ML researcher who likes Qwen and distrusts launch posts.

## What I recomputed

- **The counts hold.** The registered scorer on my copy gives 26 right, 0 wrong and 2 unfinished of 28, questions 100 to 127, one decoding, one limit. Strict and normalised marking agree, because all 26 replies are the bare station name. Without questions 103 and 108 the count is 24 right of 26.
- **No question was cut.** The log ends with `DEADLINE` after question 127 was saved.
- **The paired rows.** With reasoning off the same 28 questions gave 16 right, 10 wrong and 2 unfinished. Ten questions moved to right and none moved away from right. The first 28 are not easier than the rest: reasoning off scored 16 of 28 on them and 54 of 100 overall, and their trips are a little longer (4.4 stops on average against 3.9 for the other 72).
- **The two unfinished rows.** I read both. In question 102 Qwen closed the reasoning at token 8,000 and was cut while writing the reply, which had already said "You are now at Wall St". In question 121 the limit came inside the reasoning, on the line "Final: Green", after "Stop 2: Greenpoint Av". The lead's observation is right, and it belongs in no count.
- **One figure needs a correction before it is published.** `score_think.py` line 123 takes `new[len(new) // 2]`, which for 28 values is the upper of the two middle values. The median of the 28 token counts is 4,372, and 4,594 is the 15th value. The mean, 4,578, is right. I suggest "about 4,500" on the page and "mean 4,578, median 4,372" in the README.
- **The decoding's name.** Qwen's card calls the setting that ran "thinking mode for precise coding tasks (e.g. WebDev)". The page and README should use the card's words, because a reader will look the setting up. The card's setting for general tasks (temperature 1.0, presence penalty 1.5) did not run.
- **Reasoning is Qwen's default.** The card says that Qwen3.5 models "operate in thinking mode by default". So every reasoning-off number on the page was measured with Qwen's default mode switched off. My reader knows this already.

## 1. What 26 of 28 does to the post's argument

The post makes its case in three steps. The first step is the motive: models get lost on the subway, and models are catastrophically bad at reading the map. The second step is the demonstration: the graph-qwenputer answers exactly. The third step is the meaning: a language model can hold exact facts, and a sentence can change them.

The result removes the second half of the motive. With the right lines in the prompt and reasoning on, Qwen was right on every question that Qwen finished, and Qwen did not finish 2 of 28. The result also changes how the chart reads. Before, the chart showed a gap that the graph-qwenputer closed. Now a stock Qwen bar stands within two questions of the graph-qwenputer's bar, and the saved rows say that Qwen spent about the same number of tokens (section 2).

The demonstration and the meaning are untouched as facts. Every claim about the graph-qwenputer rests on its own saved results, and none of those results needed Qwen to fail with the map. The post already says that accuracy is not a reason to build the graph-qwenputer. So the result costs the post one bad reason and leaves the good reason standing.

The risk is in how the page handles the change. If the page removes one sentence and adds one bar, my reader will see a post that led with a claim, lost the claim, and carried on. The page should instead say the new fact early and in plain words, and then rest on the closing claim. I gave that order in my pre-run review, and the result now calls for it.

My reader's next question will be this one: "The prompt also holds facts exactly, and a sentence in the prompt also changes them. Did you test Qwen with the map in the prompt and reasoning on, on a closure or a new line?" The answer is no, and the registration closes the reasoning-on baselines after this revision. The page should say so before the reader asks.

### Sentences that now read as wrong, unfair or unearned

| Where | The sentence | Why | What I would do |
|---|---|---|---|
| `template.html` 218 | "And models are catastrophically bad at reading the subway map without help." | Wrong for Qwen with reasoning on. The registered rule removes it. | Replace the paragraph, 4(a). |
| `template.html` 213, and `web/make_article.py` 100 | "Large language models get lost on the subway." | Unearned whatever arm A shows. One model of 4 billion parameters ran, and the registration of 9 Nov says the opening's claim stays about Qwen 3.5 4B. With the lines in the prompt Qwen does not get lost. | Held for arm A. Wording in section 4. |
| `template.html` 216 | "Give a language model called Qwen 3.5 a few stops to follow on the New York subway, and Qwen will tell you with total confidence that you've arrived somewhere you haven't." | Unfair without "from memory" and "with reasoning off". "Total confidence" is partly made by the prompt, which allows the station name only. | Held for arm A. Add "from memory" at the least. |
| `template.html` 234 | "Qwen answered straight away with no sign of doubt." | The question forbade any sign of doubt, and the test switched off Qwen's default mode. | Say that reasoning is Qwen's default. Add arm A's counts here. |
| `template.html` 244 | "The chart shows how each version did on the same 100 questions." | No longer true once a bar covers 28 questions. The chart's `aria-label` says the same. | "The bars for Qwen with reasoning on cover the first 28 questions, which is as far as my time limit reached." |
| `template.html` 244 | "Qwen's reasoning stayed off for that test too, and I tried only one prompt, so Qwen might do better with another setup." | Now coy. I know that Qwen does better. | Replace, 4(b). |
| `template.html` 244, the trip picker | The rows "Qwen alone" and "Qwen, map in prompt", and "Orange marks show the stations Qwen named without the graph-qwenputer". | The six trips are questions 100 to 105. The picker shows Qwen with the map wrong on 3 and unfinished on 1. With reasoning on, Qwen was right on 5 of the same 6 and unfinished on 1. This is the most visible unfairness left after the sentence goes, because readers play with it. | Label both rows "reasoning off". Add a row "Qwen, map in prompt, reasoning on" from `P.jsonl`. Say that the orange marks are reasoning-off answers. |
| `template.html` 244 | "An ordinary tool outside the model, given the same queries, scored the same as the graph-qwenputer both times, so accuracy is not a reason to build the graph-qwenputer." | True, and now incomplete. Qwen itself comes close. | Add "and Qwen with the map and reasoning on came close". |
| `template.html` 269 | "With the map pasted in, I asked Qwen to list each stop before answering, and Qwen got 54 of 100 right, got 36 wrong and did not finish 10." | Used as evidence against memorising. A map-in-prompt score says nothing about memory, and the number is the reasoning-off one. | Replace, 4(c). |
| `template.html` 226 | "On the sealed map with invented names, Qwen alone got 0 of 100, and Qwen with the graph-qwenputer printed 296 of 300 right" | True, but unearned as a contrast. No model can know invented names. The row is a control for memory. The fair baseline, Qwen given the invented map's lines with reasoning on, did not run. | Add "with no map and reasoning off", and present the 0 as a check that Qwen cannot know the names. |
| `template.html` 259, 272 | "Qwen's judgment is still the weak part." | The code I read passes `enable_thinking=False` in the graph-qwenputer's own flows (`tok/common.py` 45, `exec/common.py` 40, `ctrl/flows.py` 70). If that holds for the exams, every judgment number (13 of 30 wrong closes, 0 of 10 after pushback, 225 of 300 replies) is a reasoning-off number. After this result my reader will discount all of them. I did not trace every exam script, so please confirm. | Say once, in this FAQ answer and in the README's known problems, that Qwen's reasoning was off in those tests and that reasoning on was not tested. |
| `README.md` 226 | "Qwen alone, no map, 600 questions \| None \| Stock Qwen \| 10 right." | The row does not say reasoning off. Line 308 says so, eighty lines later. | Put "reasoning off" in the row. |
| `README.md` 227 | "Qwen given the map and asked to list each stop before answering, reasoning off, 100 questions … 54 right, 36 wrong, 10 unfinished at 1,024 new tokens" | True. Alone, it now misleads. | Add the reasoning-on row under it, and the paragraph 4(e). |
| `README.md` 324 | "The first sitting's printed line gave 0 wrong and 53 refusals, where Qwen with the map gave 36 wrong; a normal tool refuses the same way." | The contrast needs "with reasoning off". With reasoning on Qwen gave 0 wrong on 26 finished. | Add both. |
| `release/launch-posts.md`, X thread 5 | "Alone, Qwen got 0 of 100 there." | Same point as the sealed map above. | Add "with reasoning off", or cut. |
| `release/model/README.md` | None. | The model card makes no claim about Qwen and the map. | No change. |

The still article, the Word copy and the Medium, Substack and LinkedIn drafts carry the same sentences. `web/OBJECTIONS.md` row 7 also cites "map-in-prompt 54 of 100" as an answer to memorising.

## 2. The honest comparison of cost

All numbers are from saved rows. The graph-qwenputer's rows are the fixed build's 300-question exam on the real model (`exam/results/after/stock_d1m0` to `stock_d1m2`), filtered to the same 28 questions.

| On questions 100 to 127 | Qwen, map lines in prompt, reasoning on | Graph-qwenputer, fixed build |
|---|---|---|
| Right, wrong, unfinished or refused | 26, 0, 2 | 28, 0, 0 (printed line) |
| New tokens a question, mean | 4,578 | 5,402, of which about 51 are Qwen's |
| New tokens a question, median | 4,372 | 5,358 |
| New tokens a question, range | 745 to 8,192 | 4,812 to 6,545 |
| Prompt tokens | 591 to 1,076, mean 854 | 1,398 to 1,405 |
| Seconds a question, as saved | 309, at 15 tokens a second, with a game on the GPU | 87, at 62 tokens a second, on 4 Nov |

**Yes, stock Qwen with reasoning now does the two-train trip for about the same tokens.** On the mean Qwen used about 15% fewer. Qwen used fewer tokens than the graph-qwenputer on 16 of the 28 questions and more on 12. Qwen's cost varies elevenfold, and the graph-qwenputer's cost stays within a narrow band. On the current build the same kind of trip costs a little more: 6,279 tokens for the walkthrough trip, and a median of 5,871 machine tokens on the sealed map's 100 two-train questions (`s2_nyc-relabelled`, simulator).

Reasoning itself is dear. With reasoning off and the list-each-stop prompt, the same 28 questions took a mean of 337 new tokens. Reasoning on took about 14 times as many, and moved the count from 16 to 26.

The page's line "The graph-qwenputer is slow" stays true against an ordinary tool. Against Qwen's own reasoning, the graph-qwenputer is about level in tokens on this trip. The page should say that, because a sceptic will work it out from two numbers that are both public.

**What I could not verify.**
- A fair time. The two runs were on different days under different loads. A machine token passes through 11 layers and a Qwen token through 32, so the rates differ by design. At the 23.3 tokens a second that the reasoning-off run measured, 4,578 tokens would take about 196 s. That is my arithmetic and no run measured it.
- Whether the 4 Nov seconds include the first pass over the prompt, and what else used the Mac. The run's `meta.json` says `shared_gpu: unknown`.
- The current build's cost on these 28 New York questions on the real model. No saved run has it.
- The whole map in the prompt. No test put it there. The 52 line lists that appear across the question file's prompts total 22,044 characters, which is about 9,000 prompt tokens at the ratio in the saved prompts. That is my estimate.

**What the graph-qwenputer does that Qwen with reasoning was not tested on.** Qwen with reasoning ran 28 trips of 2 to 6 stops with one change, with the 4 or 6 needed lists handed over. Nothing else ran. The saved results for the graph-qwenputer cover more ground:
- Routes that need a search: 39,584 tokens for the 10-step route, 58,901 around a closure, and 3,000 routes with stops closed on the simulator, none through a closed stop.
- A closure or a new line said in a sentence, kept across turns: 40 of 40 closes, 35 of 40 reopens, 3 of 3 new lines, and the map read back byte for byte (52,519 bytes, 0 differ).
- Shared names: 47 of 47 on the sealed map.
- Exactness at a scale that 28 questions cannot reach: 995,198 machine calls with 0 differences, and refusals in place of guesses (0 wrong and 53 refused on the first exam).
- The map held in the running memory, with no map text in the prompt.

Two cautions for the wording. "No wrong answers by construction" is true of the machine given a right query. It is not true of Qwen plus the machine: the page reports 1 clean wrong of 100 on new wordings and 9 wrong of 100 on harder wordings. And "no map in the prompt" did not make the prompt shorter on this task: the tool prompt is about 1,400 tokens, and the pasted lines made prompts of 591 to 1,076.

**The honest reason to build that remains** is the one in the closing section and in the README's "Why bother?": an exact part inside a model's own run, with a memory that a sentence changes and that reads back exactly. Round 18 takes away a reason the post never needed.

## 3. How the page should state the limits

So that the reader does not overread the bar:
- Give counts, "26 of the first 28", and never a bare percentage.
- Draw the bar as shares of its own 28, and put "first 28 questions" in the label.
- Say that the prompt held only the lines the trip needs. Qwen did not have to find those lines in a whole map.
- Say that the reasoning-on bar differs from the reasoning-off bar in four things: reasoning, the prompt, the decoding and the limit. The pair of bars does not isolate reasoning.
- Say that each question ran once with some randomness. Another seed could move the count.
- Say that this is one model.

So that the reader does not underread the bar:
- Say that the same 28 questions gave 16 right with reasoning off.
- Say that Qwen gave no wrong answer.
- Say, as a hand reading, that both unfinished replies had reached the right station, and that the card recommends four times the limit.
- Keep the caveats short. Five sentences of caveats under a 26 of 28 would look like an effort to shrink it.

On intervals: 26 of 28 has an exact 95% interval of 76% to 99%. None wrong of 26 finished is consistent with a true wrong rate of up to about 13%. I would print the intervals in the README and leave them off the page, which prints no other interval. The interval treats the question as the unit and ignores the one sample a question, so the README should say that too. The 90% line in the registered rule was met at 26 of 26, and the lower bound on that share is 87%, so the page should not present 90% as a measured boundary.

All three changes that I chose on the practice questions (prompt, decoding, limit) help Qwen finish. They work against the post's old claim. The page can say so in one clause, and it will earn trust.

## 4. Proposed wording

**(a) The paragraph that holds "catastrophically".**

> So I loaded Qwen with the New York subway. The subway map is a good test for three reasons. Stations close and reopen. There are many ways from one place to another. And anyone can check an answer against the map. With the right lines of the map pasted into the prompt, and with reasoning turned on so that Qwen works through the trip in writing before answering, Qwen follows a trip well: Qwen got 26 right of the 28 questions that I had time to run, got none wrong and did not finish 2. So the question for this post is whether a model can hold the whole map exactly, and change the map when a person says so.

If the first screen cannot take the length, end the fourth sentence after "follows a trip well" and keep the counts for step 14. The last sentence uses the closing section's own verb, "hold", on purpose.

**(b) The step-14 paragraph that begins "Qwen alone got 1 right."**

> With no map and reasoning off, Qwen got 1 of the 100 questions right. **[ARM A: With no map and reasoning on, Qwen got __ right of the first __ questions, got __ wrong and did not finish __ within 8,192 new tokens.]**
>
> With the map, Qwen does much better. I pasted the lines of the map that each question needs into Qwen's prompt. With reasoning off, I asked Qwen to list each stop before answering, and Qwen got 54 right and 36 wrong, and did not finish the other 10 within my limit of 1,024 new tokens. With reasoning on, I had time to run the first 28 of the 100 questions. Qwen got 26 right and none wrong, and did not finish the other 2 within my limit of 8,192 new tokens. With reasoning off, Qwen had got 16 of the same 28 right.
>
> The two tests with the map differ in more than the reasoning. With reasoning on, I left out the instruction to list each stop, because with that instruction Qwen did not finish a practice question within 8,192 tokens. Qwen also chose each token with some randomness, at the setting that Qwen's model card gives for precise coding tasks, and I ran each question once. With reasoning off, Qwen always printed the most likely token. I chose the prompt and the setting on two practice questions, by whether Qwen finished and how many tokens Qwen used. Qwen's model card recommends a limit of 32,768 tokens, so Qwen might finish the other 2 with a longer limit. I tested one model, with one prompt for each test.
>
> Reasoning costs tokens too. With reasoning on, Qwen wrote about 4,500 new tokens for each question, and the graph-qwenputer took about 5,400 tokens for each of the same 28 questions.

The third paragraph holds every item the registered rule requires and nothing more. The fourth paragraph is my addition, and it can also sit beside "An ordinary tool does the same job in milliseconds" at step 9.

**(c) The FAQ answer "Did Qwen just memorize New York?"**

> No. I trained nothing. Qwen's 32 layers still hold Qwen's released weights, in wider layers that make room for the computer, and the technical notes below give the exact comparison. With no map and reasoning off, Qwen got 10 of 600 right. **[ARM A: With no map and reasoning on, Qwen got __ of the first __ two-train questions right.]** On the sealed map with invented names, which Qwen cannot know, the graph-qwenputer printed the right answer on 296 of 300 questions, with the 11 added layers on the simulator. On the simulator, with an invented city's map loaded, the graph-qwenputer got 0 of New York's 600 questions right, so the answers come from the map in the running memory. Reading a map from the prompt is a separate skill, and with reasoning on Qwen does that well: 26 right of the first 28 two-train questions, none wrong and 2 unfinished.

**(d) The label of the new chart bar.** `web/chart.py` already draws a smaller second line under a label, so the registered items fit on two lines.

> Qwen given the map, reasoning on, first 28 questions

> One sample a question at temperature 0.6, limit 8,192 tokens

The first line is 52 characters, the same as the longest label on the chart now. By Helvetica's widths the first line is about 307 px at 13 px, and the second line is about 325 px at 12 px. I could not render either, so please check both in a browser at 380 px and on a phone. Arm A's bar can use "Qwen alone, no map, reasoning on, first __ questions" with the same second line. Put each reasoning-on bar directly under its reasoning-off bar.

**(e) A short README paragraph.**

> **Qwen with the map and reasoning on (round 18).** I reran the chart's map baseline on stock Qwen3.5-4B with reasoning on, which is Qwen's default mode. The prompt held the lists of stops for the two trains in the question (4 lists, or 6 where a line branches; 591 to 1,076 prompt tokens) and the question as written, with no instruction to list each stop. I took one sample a question at the model card's setting for precise coding tasks (temperature 0.6, top-p 0.95, top-k 20, no presence penalty), with a limit of 8,192 new tokens where the card recommends 32,768. I chose that prompt and that setting on two practice questions outside the exam, by whether Qwen finished and how many tokens Qwen used, and never by whether an answer was right. With the list-each-stop instruction Qwen did not finish a practice question, and with the plain question Qwen finished both. The practice questions use the map lines of exam questions 103 and 108, and without those two the count is 24 of 26. The run's 8,500 s covered the first 28 of the 100 questions: 26 right, 0 wrong and 2 unfinished at the limit, against 16, 10 and 2 for the same questions with reasoning off. Qwen wrote a mean of 4,578 new tokens a question, where the fixed build's exam took a mean of 5,402 on the same questions. The two map rows differ in prompt, decoding and limit as well as in reasoning, and this is one model with one sample a question. A first attempt with the list-each-stop prompt and a 2,048-token limit ran 10 questions before the Mac went to sleep, and Qwen finished none of them. Rows: `exam/results/after/think2/P.jsonl` and `exam/results/after/think/M.jsonl`.

**The opening line.** "Large language models get lost on the subway." cannot stand as written in either case. The plural is the problem, and arm A cannot fix it.

If Qwen alone still fails with reasoning on:

> Without a map, the language model Qwen 3.5 gets lost on the subway. So I loaded New York's map into a computer that lives inside Qwen. Now a sentence can close a station or open a new line, and the computer finds the new route.

If Qwen alone does well, the registered rule asks for the count, and "gets lost" has to go:

> From memory, the language model Qwen 3.5 got __ of __ subway trips right, and Qwen's memory cannot change when a station closes. So I loaded New York's exact map into a computer that lives inside Qwen. Now a sentence can close a station or open a new line, and the computer finds the new route.

The second version also works in the first case, because the page's FAQ already says that weights do not change while a model runs.

## 5. What the author should say first

1. **"Until 10 Nov this page said that models are catastrophically bad at reading the subway map. That rested on a test with reasoning off, and I removed the sentence."** One dated sentence on the page, and a row in the README's table of misses, as the README did for "bit-identical".
2. **Reasoning is Qwen's default mode,** and the earlier tests switched the default off.
3. **The first attempt.** Ten questions, a 2,048-token limit, the list-each-stop prompt, none finished, and the Mac asleep. Its two predictions failed, so they belong in "Predictions that missed". The revision is the one allowed revision, and each change in the revision helps Qwen.
4. **Twenty-eight questions, one sample each,** the first 28 in file order, because the time ran out.
5. **The prompt held only the needed lines,** and the whole map was never in a prompt.
6. **The token cost is about level.** Say it before a sceptic divides one public number by another.
7. **What was not tested with reasoning on:** closures, new lines, long routes, shared names, the sealed maps, and Qwen's judgment in the graph-qwenputer's own conversations.
8. **The setting is the card's setting for precise coding tasks.** The card's general setting did not run.
9. **Where Qwen ran out of tokens, Qwen was arguing with the map.** In both unfinished rows the reasoning weighs the map's direction labels against Qwen's own memory of the city, and that memory is partly wrong. Question 102's reasoning says that the 2 train "runs between Queens … and Brooklyn", and question 121's calls the 7 train's "southbound" label inconsistent with geography. This is a hand reading of two rows, and it supports no count.

## Held for arm A

The dek, the first intro paragraph, step 4, arm A's bar and its place in the chart, the gaps in 4(b) and 4(c), and X thread 5. I will also check whether Qwen, with room to reason, shows doubt before it names a station, because that decides whether "total confidence" can stay.

## Second pass: the draft wording

10 Nov, about 15:00 ET. I read `draft18/out/changes.md` (all 21 passages, the README ones included), `draft18/apply.py`, `draft18/after_section.md`, and the changed passages of `draft18/out/template.html` and `out/index.html` in their context. I wrote nothing outside this file. Arm A is still running, and I did not open its rows.

### 1. Does the draft do what my reader needs, in the right order?

Mostly yes. The first screen now claims nothing that the rows do not support, step 14 gives the new counts as a result of equal standing, the token cost is on the page, the picker shows the reasoning-on reply, and the new question holds the setup, the dated correction and what was not tested. Leaving out my framing sentence does not fail my reader. The second intro paragraph already states the aim ("to see whether a real-world graph problem could live inside the model itself"), and offering the sentence to Theo as an option is the right call.

A sceptic would still say four things first.

1. **"You switched off Qwen's default mode at step 4, and the page tells me that reasoning is the default only in a folded question at the bottom."** The term is also used before it is defined: "reasoning off" first appears in the box at the top, then at step 4, and the definition comes in the last third of the page. Move the definition sentence from the new question to step 4, where the test is described. The move costs no extra sentence.
2. **"Your dek says Qwen gets lost without a map, and your own test with reasoning on decided nothing."** See section 3.
3. **"The first bar now shows 11 grey replies, and the text does not say what they are."** `apply.py` redraws the bar as 1 right, 88 wrong and 11 unfinished. The paragraph under the chart gives only the 1.
4. **"The closing says that Qwen's judgment is the weak part, and those tests had reasoning off."** The draft's covering sentence sits at the end of a question about trips. If the critic's trace confirms the sentence, also add four words where the judgment numbers are, in "Does the graph-qwenputer make Qwen reliable?": "On the current version, with Qwen on the real model, **with Qwen's reasoning off** and the 11 layers on the simulator, …".

One smaller point is Theo's to decide. Once the first paragraph says that Qwen had no map and no chance to work the trip out, "silly mistakes" in the sentence before reads oddly, because the next sentence explains why the mistake is expected.

### 2. Wording, passage by passage

| Passage | Verdict | Replacement |
|---|---|---|
| The line under the title, and the still article's | Fails on substance, section 3 | "Asked to answer straight away with no map, the language model Qwen 3.5 gets lost on the subway." |
| First paragraph, "with no map and no time to reason" | Reads unfairly. Nothing limited Qwen's time. I switched a mode off and the question allowed the name only, so "no time" turns my setting into a circumstance. "To reason" also uses the page's defined term in its everyday sense, two paragraphs before "two reasons" and long before the definition. | "with no map and no chance to work the trip out in writing first" |
| Third paragraph, two reasons | Passes. | |
| The box, "Qwen with no map and reasoning off got 0 of 100" | Uses "reasoning off" before the page defines reasoning. Nobody can know invented names in any mode, so the two words add nothing here. | "Qwen with no map got 0 of 100" |
| Step 4 (not in the draft) | "Reasoning" is used here undefined. | Add before "For this test I turned off Qwen's reasoning": "Reasoning is Qwen's default mode, in which Qwen writes out working before answering." Delete the same sentence from the new question. Without "its", by the rule. |
| Step 14, the sentence before the chart | The second sentence says what the bar's label and the paragraph under the chart both say. | Cut the second sentence. Keep "The chart shows how each version did on those questions." |
| Step 14, the caption | More than the page needs. The label says "first 28 questions" and the bar prints 26 and 2. | Cut the added sentence. |
| Step 14, "With no map and reasoning off, Qwen got 1 of the 100 questions right." | True, and now short of the chart. | "With no map and reasoning off, Qwen got 1 of the 100 questions right and 88 wrong, and my limit of 40 new tokens cut off the other 11 replies." |
| Step 14, "Qwen did much better" | Passes. The counts that follow carry it. | |
| Step 14, "With reasoning on, I had time to run … and Qwen got 26 right and none wrong, and ran out of tokens on the other 2." | Three "and"s in a row. The limit is missing, where the sentence before gives 1,024. "Ran out of tokens" and "did not finish" name one outcome in two ways, and a reader will think they differ. | "With reasoning on, I had time to run the first 28 of the 100 questions. Qwen got 26 right and none wrong, and did not finish the other 2 within my limit of 8,192 new tokens." |
| Step 14, "The two tests differ in more than the reasoning, and the questions at the end of this post say how." | Passes. | |
| Step 14, the ordinary tool, "came close" | Passes. The counts are two paragraphs above. | |
| Step 14, "The cost in tokens is close too. With reasoning on, Qwen wrote about 4,600 new tokens for each question, …" | The figures are means, and Qwen's range is 745 to 8,192. The tense should match "came close". | Write "was" for "is" in the first sentence, and begin the second sentence with "On average,". |
| The picker's sentence and rows | Pass. In the build, write the two unfinished replies the same way: "(did not finish within 1,024 tokens)" and "(did not finish within 8,192 tokens)". | |
| The question about memorizing | Passes. | |
| New question, "For the two-train trips, nearly." and the two sentences after | A fragment, and the verdict leaves out the condition. With no map the answer is not "nearly". The third sentence repeats step 14. | One sentence for the three: "With the right lines of the map in Qwen's prompt and Qwen's reasoning on, Qwen got 26 of the first 28 two-train questions right and none wrong, and did not finish the other 2 within my limit of 8,192 new tokens." |
| New question, arm A | The question in the title is not answered for the case with no map. | Repeat step 14's arm A sentence here, after the counts. |
| New question, "Reasoning is Qwen's default mode, in which Qwen writes out its working before answering." | Right sentence, wrong place. | Moved to step 4, above. |
| New question, the correction ("Until 10 November … I removed the sentence.") | Passes, and it is the sentence that earns the most trust. | |
| New question, "With reasoning on, I gave Qwen the lists of stops … I left out the instruction to list each stop, because with that instruction Qwen did not finish a practice question." | Both tests gave the lists, and the sentence reads as if only one did. "Did not finish a practice question" is looser than the row: the practice run that reached the limit was the most-likely-token run, and the run at the chosen setting was stopped at 6,000 tokens. | Write "the same lists of stops" in the first sentence. Then: "I left out the instruction to list each stop, because with that instruction Qwen used all 8,192 tokens on a practice question without answering." |
| New question, "Qwen's model card gives", "Qwen's model card recommends" | "Model card" is never defined on the page. The sentence also names only one side of the fourth difference. | In both sentences write "Qwen's makers recommend" for "Qwen's model card gives" and "Qwen's model card recommends". After "and I ran each question once." add: "With reasoning off, Qwen always printed the most likely token." |
| New question, the four ways, the practice questions, one model, what was not tested, "every other test" | Pass. The last waits for the critic's trace. | |

Three notes on the README passages, which follow the README's looser style and otherwise read well. "What that result can't carry." is a fragment standing as a sentence, so make it a bold label like its neighbours. "About a tenth of the map" should be "about a tenth of the map's lists of stops", because the 52 lists are what the tenth is measured against. And the README's candid account of the practice rule ("That rule wasn't even-handed") is why the page's sentence about the practice question should match the row exactly, as in the table above.

### 3. Can the dek say "gets lost" while arm A is undecided?

It can say "gets lost" only for the condition that was measured. The registered rule for an arm A of fewer than 25 questions is that the page gives the three counts and makes no claim from them. Question 100's row is one of those counts, so the row cannot hold up the dek, however plainly it shows Qwen failing to recall the M train's stops. The reasoning-off rows can hold up the dek (10 of 600, 1 of 100), and then the dek has to say which condition they are. The map arm's rule did the same thing for its undecided case: the sentence was to be limited to reasoning off. "Without a map, the language model Qwen 3.5 gets lost on the subway" has no such limit, and a desktop reader meets it before any limit appears. On a phone the dek is hidden, and the first paragraph, which is limited, comes first.

My reader thinks the unlimited claim is very probably true. A model of this size is unlikely to recite 496 stops in order from memory. The post has refused "very probably true" everywhere else, and the limit costs five words:

> Asked to answer straight away with no map, the language model Qwen 3.5 gets lost on the subway. So I loaded New York's map into a computer that lives inside Qwen.

"Asked to answer straight away" is step 4's own phrase for the test, and it needs no defined term.

**The bar for arm A.** "No bar unless Qwen gets several right" makes the drawing depend on the result. The dependence runs against the author's interest, and a sceptic will still call it a choice made after the rows. Decide by n instead, and write the decision into `exam/AFTER.md` before the arm ends: with fewer than 25 questions, the three counts go in the text and no bar is drawn, whatever the counts are. A bar of 6 or 7 questions at full width would be a claim, and the rule says to make none.

A sentence for the gap, if the lead wants one: "With no map and reasoning on, my time limit reached only __ questions, which is too few to decide anything: Qwen got __ right and __ wrong, and did not finish __ within my limit of 8,192 new tokens."

### 4. Is anything more than the page needs?

Five things, all small. The second sentence before the chart and the caption's added sentence both repeat the label. The new question's third sentence repeats step 14. The definition sentence moves and is not doubled. "And reasoning off" in the box goes. Everything else in the second paragraph of the new question is something the registered rule requires the page to say, so that paragraph stays. The two sentences on token cost stay too, because a sceptic can work the comparison out from two public numbers.

The cuts and the additions in section 2 balance, so the page ends about as long as the draft is now.
