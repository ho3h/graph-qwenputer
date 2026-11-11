# Round 18 pre-run critical review

**Verdict: RUN AFTER FIXES.** 9 Nov, CPU only: `think.py --dry`, a scratch copy of its loop on a stub model, `score_think.py` on invented rows, `import flows`, `zsh -n`.

## Blockers

**1. The page rules count unfinished rows as failures (`exam/AFTER.md:453`).** Decoding is greedy with a 2,048 cap. The model card (`~/Models/x210/Qwen3.5-4B/README.md:835`, `1145-1147`) gives temperature 1.0, top_p 0.95, top_k 20 and presence_penalty 1.5 for reasoning, names "endless repetitions", and recommends 32,768 output tokens. As written, arm A at 3 right, 20 wrong, 77 unfinished prints "fails with reasoning on too", and arm M at 70 right, 5 wrong, 25 unfinished keeps "catastrophically bad" though 70 of 75 finished answers were right. The thresholds are undefined when a deadline cuts an arm.
Fix, text only: thresholds are shares of the rows that ran. The "fails" sentence needs unfinished at or under 40%; above that, the page gives the three counts and no claim. The arm M phrase also comes off when right / (right + wrong) is 0.9 or more. Both bars join the chart whatever they are. Labels say "greedy, 2,048-token cap", and the page says the card's settings were not used.

## Should fix

**2. The deadline will probably cut (`queue27.sh:21,25`, `AFTER.md:449`).** M1's cap rows ran 25 tokens a second, so 2,048 tokens take 81 s and 6,000 s covers 74 questions at worst. S2's 56 rows need about 720 s (12.5 s a row on 5 Nov), not 3,700. Fix: deadline 6,900, hard stop 7,000, guards `0602`; S5 still ends by 07:41 if S2 takes 12 minutes. Also register: a cut arm is compared with the reasoning-off rows of the same ids.

**3. Arm M's generous count is not `score_mapped.py`'s (`score_think.py:37`).** It searches the whole reply, which holds the stop list. On M1's own rows that rule gives 68, against the saved 54. Fix: `want in (text if arm == "A" else ans)`, and `AFTER.md:447`.

**4. Cap hits change category between bars.** `score_after.py` has no unfinished: 11 of the chart's 99 wrong reasoning-off replies were cut at 40 tokens. `score_mapped.py:24` counts a right `Answer:` line at the cap as right; `score_think.py:36` calls it unfinished (M1 had none). Fix: redraw the first bar as 1, 88, 11, or say so under the chart.

**5. No restart after a crash (`queue27.sh:21,25`).** An MPS error or memguard kill at question 30 loses the arm, though `think.py` resumes. Fix: `exam/mapped.sh`'s loop: rerun while the code is not 0 or 3, three restarts at most, `--deadline-s` set to the seconds left, `>>` the log. Register it.

**6. Nothing keeps the Mac awake (`pmset`: sleep 1).** Fix: after line 4, `caffeinate -is -w $$ &`. Launch from X2.10 as `nohup zsh exam/queue27.sh > exam/results/after/queue27.log 2>&1 &`. `stop_q27.sh:3` matches only that form; otherwise the queue survives and starts the next step.

**7. Line 13 sees only another project.** The GPU's user now is a game (pid 88101). Open at 02:15, it slows both arms, and S5 needs 32 tokens a second (r6e ran at 28 with company: 5,287 s against S5's 4,700). Fix: ask Theo to quit it; log the top CPU users at start.

## Minor
- Guards read minutes: 06:18:59 + 6,100 s is 08:00:39. Use `0617`, `0657`.
- `score_think.py:19`: a truncated last line throws and loses both scores.
- Arm M is the one-flag counterpart: the list is written twice inside the cap. Keep "listing each stop" in the label.

## Holds
- Ids 100 to 199 in M1's order; `alone.jsonl`'s text equal on all 100.
- All 100 arm M prompts tokenize to M1's saved `prompt_tokens` with reasoning off; on and off differ only after `<think>`.
- `</think>` is 248069; zero reasoning tokens handled; stops as before.
- Loop, cap, resume, `--limit`, deadline exit and rows pass on the stub.
- `del cache; FL.torch.mps.empty_cache()` equals `mapped.py:62-63`; `enable_thinking=True` works.
- Memory: M1 flat at 10.6 GiB; 4,700 s single-process runs peaked at 8.9.
- Strict marking equals both older scorers on finished rows.
- Queue: dates, the spaced path, `timeout`, step isolation. S2 appends; its 244 keys are a prefix of the draw, same firmware. `stop_q27.sh` touches only X2.10 patterns.
