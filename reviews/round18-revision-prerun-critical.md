# Round 18, the one revision: critical pre-run review

10 Nov. Reviewed: `exam/AFTER.md` lines 442 to 504, `exam/think.py`, `exam/card_sample.py`, `exam/queue28.sh`, `exam/score_think.py`, `tools/memguard.py`, `host/model.py`, the model card, the 10 saved rows of the first attempt. I ran `card_sample.py` (9 checks pass), both `--dry` prompts, and plain Python over saved rows. I did not load the model, and I did not open `think2/` or `think2_dev/`.

Findings are ranked, most serious first. "Changes rows or scores" is answered for each.

## 1. The budget uses a speed the first attempt did not reach. The run can end with too few questions to decide anything. (must fix)

`exam/AFTER.md:494`, `exam/queue28.sh:18,23,31,32`.

The registration says 23.3 tokens a second, so 352 s for 8,192 tokens, and "at worst 8,700 s covers 24 questions". The first attempt's own rows say otherwise. Before the lid closed, with a game at 145% CPU (`results/after/queue27.log`), rows 100 to 102 ran at 10.5, 12.7 and 15.7 tokens a second. Rows 103 and 104, after the lid closed, ran at 23.5 and 22.1.

| Speed | 8,192 tokens | Arm M rows saved in 8,700 s, every question at the cap | Arm A rows saved in 4,300 s |
|---|---|---|---|
| 23.3 tok/s | 352 s | 25 | 13 |
| 15 tok/s | 546 s | 16 | 8 |
| 10.5 tok/s | 777 s | 11, and a 12th cut by the hard stop | 6 |

At 14 tokens a second, with half the questions finishing at 3,000 tokens and half at the cap, arm M reaches about 22 questions. The registration's own rule then says the arm decides no wording, and there is no second revision. The run is in the daytime, when the Mac is in use.

Two more consequences:
- The hard stop is the deadline plus 450 s. `think.py:124` starts its clock after the model loads, so a question that starts just inside the deadline has 450 s minus the load time. Below about 20 tokens a second, such a question is killed if it runs to the cap, and its row is lost.
- The question the hard stop kills is always a long one, so it would most likely have been unfinished. Dropping it lowers the unfinished share by one question in each arm. At 25 questions that is 4 points, next to a 25% threshold.

Changes rows or scores: it changes which questions run, whether any page rule fires, and the unfinished share by one question an arm.

Fix, before launch:
1. Read `seconds` and `new_tokens` from the practice rows. They hold today's speed on the sampled path and the token counts at which Qwen finishes. Write both numbers into the registration.
2. Recompute the expected number of arm M questions. If it is under about 35, move time from arm A to arm M, or run arm M alone, and say so in the registration. Arm M decides the opening. Arm A at 12 questions decides nothing under the registration's own rule.
3. Set the hard-stop margin to at least 1.25 times the measured time for 8,192 tokens, and shorten the deadlines so the total stays at 13,900 s.
4. Print the question id when a question starts (`think.py:131`), so the log names any question the hard stop cut. Register now that a cut question is reported by id and counted as not run.
5. Look at the busiest processes before launching, not only in the log afterwards.

## 2. The marking counts some right, finished replies as unfinished or wrong. (must fix)

`exam/score_think.py:59-61` (arm A), `:65-67` (arm M).

I ran the script on made-up rows in my scratch folder. Each of these replies came after closed reasoning, and Qwen stopped by itself:

| Arm | Reply after the reasoning | Marked |
|---|---|---|
| M | `**Answer**: Wall St` | unfinished |
| M | `Final answer: Beach 105 St` | unfinished |
| M | `57 St-7 Av` (name only) | unfinished |
| M | `Answer: Hoyt St` then a blank line and a note | wrong |
| M | `Answer: <Bleecker St>` | wrong |
| M | `Answer: Lafayette Av station` | wrong |
| A | `**Clinton-Washington Avs**` | wrong |
| A | `Answer: Hoyt St` | wrong |

The generous count does not rescue the first three, because on arm M it also needs the literal `Answer:`. A reader would call "unfinished" unfair for a reply that stopped with the right station. These rows also push the unfinished share toward the 25% line that cancels the wording rules.

The reasoning-off rows never used these forms: all 90 finished M1 replies have a one-line `Answer:`, and strict equals generous at 54. So the risk is small with greedy decoding. Sampled decoding at 25 or more questions makes one or two such rows plausible, and at 25 questions one row is 4 points.

Changes rows or scores: scores, yes.

Fix, registered before any row. I checked that this rule still gives 54, 36 and 10 on M1 and 1 of 100 on Qwen alone:
- Arm M: strip `*` from the whole reply, find the last `answer:` without regard to case, take the first line after it, strip `<>`, backticks, quotes and a final full stop, then compare.
- Arm A: strip `*`, backticks, quotes and a final full stop, then compare.
- Add a count of rows where Qwen stopped, the right name is in the reply, and the row is not marked right. List those rows by id in `AFTER.md`.

If the marking must stay as it is, register at least the count and the list.

## 3. Nothing stops the run from mixing old rows, a second GPU job, or battery power. (must fix)

`exam/think.py:81`, `exam/queue28.sh:14-16`, `exam/score_think.py:49-50`.

- `think.py:81` resumes from any rows in the output file. It does not check that their `arm`, `cap` and `decode` match this run. A leftover test row in `think2/M.jsonl` would be skipped and scored as part of the result. I was told not to look in `think2/`, so I could not check that the folder is empty.
- The queue checks for another project's trainer but not for another `exam/think.py`. The practice job was running when I reviewed. Two jobs on the GPU would halve the speed (finding 1).
- The queue logs the power source (`queue28.sh:15`) and carries on. A run on battery is how the first attempt was lost.
- `score_think.py` does not check that ids are unique or that every row has one `decode` and one `cap`. It does not write the decoding, the cap or the range of ids into `score.json`, and the bar's label needs all three.

Changes rows or scores: yes, if any stale row exists.

Fix:
- In `queue28.sh` before `mkdir`: stop if `think2/M.jsonl` or `think2/A.jsonl` exists, stop if `pgrep -f exam/think.py` finds a process, stop unless `pmset -g batt` says AC Power.
- In `score_think.py`: assert unique ids, one `decode` and `cap == 8192` in each arm, and write `decode`, `cap`, first id and last id to `score.json`.

## 4. The page rules overlap in places and are silent in others. (must fix, text only)

`exam/AFTER.md:486-490, 498`.

Two people could apply these differently:
- **"Finishes" in the decoding rule is not defined.** It could mean Qwen stopped before the cap, or `score_think.py`'s meaning (reasoning closed, stopped, and an `Answer:` line). Say which. Say also what a practice run that crashes counts as.
- **Arm M, right on 90% of finished questions and more than 25% unfinished.** Both rules apply. State that the unfinished rule wins.
- **Arm M, wrong on more than a quarter of finished questions and at most 25% unfinished.** No rule. State that the sentence stays and the page gives the counts.
- **Arm A, more than 12% right and more than 40% unfinished.** Both rules apply. State the order.
- **"Finished" in the share rules.** `score_think.py:82-83` uses right plus wrong, and a right answer at the cap counts as right. Say so in the text.
- **A cut arm on the chart.** The other bars are counts of 100. A bar from 25 questions needs a stated form: shares with the count written on it, beside the reasoning-off result on the same questions, which `score_think.py` already produces.
- **"Decides no wording."** Say what the page then shows: the three counts, the number run, and no claim.
- **The decoding rule picks on finishing, and the unfinished share is a registered outcome.** The choice was made on two questions outside the exam, which is fair. The page should say that the decoding was chosen for finishing. The practice questions use the map text of exam questions 103 and 108, so report arm M with and without those two.

Changes rows or scores: no. It changes what the scores do to the page.

## 5. "Fewer than 25 questions decides no wording" is a floor, and a low one

`exam/AFTER.md:498`.

The rule is sensible as a floor. Three weaknesses:
- It counts questions run. The arm M rules are shares of questions finished. 25 run with 6 unfinished leaves 19.
- At 25 questions the thresholds cannot be told apart. 23 right of 25 is 92%, with a 95% interval of 75% to 98%. The sentence would come off on a number that is consistent with the 75% line.
- The sample is one draw a question when the decoding is sampled.

Fix: apply the floor to finished questions for arm M. Print counts, never bare percentages ("23 of 25"). Add "one sample a question" to the label when the decoding is sampled.

Changes rows or scores: no.

## 6. Arm M's prompt, not the map, may cause most unfinished rows

`exam/think.py:37`, and the 10 saved texts.

In all 9 texts that reached the right station, Qwen then spent its remaining tokens asking itself whether "list each stop you pass" includes the starting station. The instruction was written for reasoning off. A sceptic will say that a reasoning-on baseline should get the map and the plain question, and that unfinished rows measure the instruction. The registration fixes the prompt, and I do not suggest changing it now. The page must say that the reasoning-on run used the list-each-stop prompt, and that the first attempt's unfinished rows were stuck on the wording of that instruction.

Changes rows or scores: no. It limits what the result supports.

## 7. `card_sample.py` `pick`: faithful to vLLM and Hugging Face. No defect found.

`exam/card_sample.py:17-27`.

- **Order.** Presence penalty, then temperature, then top-k, then top-p on the 20 kept tokens after they are renormalised, then one draw. vLLM uses that order. Hugging Face uses temperature, top-k, top-p in the same order and has no presence penalty.
- **Top-p edge.** `(cumsum - p) < 0.95` keeps the token that carries the sum past 0.95. Hugging Face and vLLM remove a token when the tail sum from it downward is at most 0.05. The two are the same set.
- **Presence penalty.** 1.5 is taken once from every token id already in the reply, reasoning included, prompt excluded. That is vLLM's and OpenAI's meaning. The `<think>` that opens the reply is in the prompt, so it is not penalised.
- **llama.cpp and Ollama differ.** Their default chain applies temperature after top-p and applies penalties over the last 64 tokens. The docstring should say "as vLLM", which it does, and the README should not say "as any runner".
- **Device and type.** `.float().clone()` gives a float32 copy on MPS, the index subtraction and `topk` run on MPS, and the softmax and the draw run on the CPU with a CPU generator. I see no fault. All 9 checks run on the CPU only. The practice run is the only test on MPS with real logits, so check that its rows have sane `new_tokens` and text before launch.
- **Ties.** bfloat16 logits are coarse, so ties at the 20th place can occur, and `topk` on MPS breaks them as it likes. Any tie-break is a valid sample. The draws are reproducible on this Mac and this PyTorch, not across machines. The saved `ids` make the marking reproducible anywhere.
- **Seeds.** `think.py:111` makes a new generator for each question from 18000 plus the id. Nothing carries from one question to the next. Arms A and M use the same seed for the same id, which is harmless.

Changes rows or scores: no.

## 8. `think.py`: smaller points

- **Restarts and samples.** A chunk restart or a crash restart does not change any question's sample. The generator, the `seen` set and the cache are all made anew for each question (`:111-112`). A crashed question is redone from the same seed, so there is no second draw after a failure. This assumes MPS gives the same logits for the same input in a new process. No saved check shows that.
- **`:81` and a cut last line.** `score_think.py` tolerates a last line cut by a kill. `think.py` does not: `json.loads` raises, the process fails three times, and the arm ends. The window is a few microseconds around a write. Fix: skip a line that does not parse, as `score_think.py:23-26` does.
- **`:52`.** The check that `</think>` is token 248069 runs only under `--dry`. Both dry runs passed today. Move the assert to after `tok = qwen.tok` (`:91`).
- **`:92`.** `</tool_call>` is a stop token, so a reply that ends on it is saved as stopped. It is unlikely. Count it in `score_think.py` if it happens.
- **`--dev`.** The gold answers are right. I rebuilt them from the map lines: Franklin Av-Medgar Evers College and 14 St. The same procedure gives the exam's gold on the 96 exam questions whose lines are not split into branches. Neither practice text is in `nyc.questions.json`, `X2.7/chases.json`, `data/` or `exam/items/`. `:76` itself checks only the 100 exam items. `--dev --limit 1` asks the first practice question only, and a second call does nothing, as intended.
- **`--dev` into the wrong file.** Nothing stops `--dev --out think2/M.jsonl`. Rows with ids -1 and -2 would then make `score_think.py` fail with a KeyError. Fix: refuse `--dev` unless the output path contains `dev`.
- **Saved fields.** `decode`, `seed`, `cap`, `ids`, `thought_tokens`, `stopped` are enough to redo the marking. `after_think` is decoded from the first `</think>` onward (`:135`), which is right.

Changes rows or scores: no, apart from the cut-line case, which ends an arm early.

## 9. `queue28.sh`: no defect in the loop

- **Syntax.** The zsh pattern test, the brace groups and the `local` line are valid.
- **Arithmetic.** 8,700 + 450 + 4,300 + 450 is 13,900 s, 3 h 51 min 40 s, under four hours. Model loads fall inside the deadlines.
- **Hard stop.** `timeout` is GNU coreutils 9.12 from Homebrew. It signals `memguard`, which kills the whole process group (`tools/memguard.py:61-66`). No orphan keeps the GPU.
- **`:25`.** The "arm finished" test works: that run of `think.py` leaves at most two `memguard` lines after the print.
- **`:27`.** Three failures end an arm. A `memguard` kill because the system's free memory fell under 15% counts as a failure, whichever program used the memory. Another program's memory use in the daytime can end an arm.
- **`:13`.** `caffeinate -is` does not hold a closed Mac on battery, as the comment says. See finding 3 for the guard.

Changes rows or scores: no.

## 10. The hand reading of the first attempt: 9 of 10 is right

I read all 10 `thinking` texts.

| Question | Gold | Right station written as the result before the cap? |
|---|---|---|
| 100 | Canal St | Yes. "Final station: Canal St." |
| 101 | Clinton-Washington Avs | Yes. "Stop 3: Clinton-Washington Avs." |
| 102 | Wall St | Yes. "The final station is Wall St." |
| 103 | Hoyt St | Yes. "the final station is Hoyt St." |
| 104 | 57 St-7 Av | Yes. "So the final station is 57 St-7 Av." |
| 105 | Lafayette Av | No. Qwen was still working out which way "R northbound" runs. The gold name never appears. |
| 106 | Bleecker St | Yes. "So the final station should be Bleecker St." |
| 107 | Beach 105 St | Yes. "Stop 3: Beach 105 St." It had not yet written a sentence calling it the final station. |
| 108 | Park Place | Yes. "I am at Park Place." |
| 109 | Fulton St | Yes. "Current: Fulton St." |

"Recounting and how to format the list of stops" is also right. In every one of the 9, most of the remaining text asks whether "pass" includes the starting station. This reading is by hand and is not a score, as `AFTER.md:479` already says.

## Verdict

Verdict: run after fixes. Must fix: (1) read the practice rows' speed and token counts, recompute how many questions each arm covers, re-split the time or widen the hard-stop margin if arm M is expected under about 35, and register how a cut question is reported; (2) harden the marking as in finding 2, or at least register the count and list of stopped replies that hold the right name and are not marked right; (3) guards in `queue28.sh` for an empty `think2/`, no other `think.py`, and AC power, and the asserts in `score_think.py`; (4) write the missing and overlapping page rules of finding 4 into `AFTER.md` before any row exists.
