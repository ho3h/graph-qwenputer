# Round 18, the one revision: pre-run steel-man (Qwen's side)

10 Nov. Read: the three round 18 sections of `exam/AFTER.md`, `exam/think.py`, `card_sample.py`, `queue28.sh`, `score_think.py`, the 10 rows of `results/after/think/M.jsonl`, the model card. Nothing run on the GPU. `think2/` and `think2_dev/` not opened.

## The three things to fix before launch

**1. The token rate. This is the one that can waste the only run.** The budget assumes 23.3 tokens a second. The first attempt's own rows say otherwise while a game is open, and it is open now (110% CPU at the time of this review; it was the busiest process in `queue27.log` at 02:15 too).

| rows | when | tokens a second |
|---|---|---|
| 100, 101, 102 | lid open, 02:16 to 02:24 | 10.5, 12.7, 15.7 |
| 103, 104 | just after the lid closed | 23.5, 22.1 |

At 12 tokens a second, 8,700 s is 104,000 tokens: 12 questions at the cap, 26 to 35 if Qwen finishes in 3,000 to 4,000. The registration's own floor is 25 questions, so arm M could decide nothing for a reason that has nothing to do with Qwen. Also, at that rate a capped question takes 680 s, past the 450 s hard-stop margin, so the last row is killed unsaved. Ask Theo to close the game for the four hours, or read the measured seconds from the practice rows (speed only) and write the re-based worst case into the registration before launch.

**2. The marking can call a correct, finished reply unfinished or wrong.** `score_think.py` needs the exact substring `Answer:` and then compares everything after it to the name.

| reply after the reasoning (gold: Canal St) | marked | generous |
|---|---|---|
| `**Answer**: Canal St` | unfinished | no |
| `**Final Answer**: **Canal St**` | unfinished | no |
| `answer: Canal St` | unfinished | no |
| the list, then `**Canal St**` with no "Answer" | unfinished | no |
| ``Answer: `Canal St` `` | wrong | yes |
| `Answer: <Canal St>` (copies the prompt's template) | wrong | yes |
| `'Answer: Canal St'` (copies the prompt's quotes) | wrong | yes |
| `Answer: Canal St station` | wrong | yes |
| `Answer: Canal St` then one more sentence | wrong | yes |

The first three count toward "unfinished", which feeds the 25% rule that stops any wording being decided. The generous count is not a safe fallback: it misses the first four shapes, and 17 of the 100 gold names are substrings of another station on their own map (`14 St` inside `14 St-Union Sq`), so it can also count a wrong answer right. Arm A has the same weakness for `**Canal St**`, because arm A does not strip `*`.

Fix, registered before any row exists: a normalised count drives the page rules, and the strict count is reported beside it. Find the last `answer` with optional `*` and a colon, case-insensitive; take the first line after it; strip `*`, backticks, quotes, `<>`, a trailing "station" and a trailing period; compare for equality. I ran exactly that over the reasoning-off rows (`mapped/M1.jsonl`): it gives 54, 36 and 10 with no row changing, so the published bar is untouched. Reasoning-off Qwen wrote a plain `Answer:` in 89 of 90 finished rows, so I expect few rows to differ. The point is that the rule is written before the rows.

**3. One outcome leaves the page overclaiming.** If more than 25% are unfinished, or fewer than 25 questions run, the rule says "no wording decided". Then "models are catastrophically bad at reading the subway map without help" stays, supported only by reasoning-off rows, next to a reasoning-on run that did not confirm it. My forecast puts that outcome at about one in three. Add to the registration: in the undecided case the sentence is scoped to what was measured ("with reasoning off") and the three reasoning-on counts sit beside it, with a hand count, labelled as one, of the unfinished rows whose reasoning had already written the right station.

In the same edit, add one sentence to "what the page keeps": the map prompt is the one written for reasoning off; it asks Qwen to list each stop it passes, and in the first attempt's saved reasoning Qwen spent much of its limit on what that instruction means.

## Q1. Is this the fairest test under 4 hours?

Close, with one real handicap left: the prompt.

- **The prompt.** "List each stop you pass" was a scaffold for a model that cannot think first. With reasoning on it is redundant, and it is the largest single sink in the saved texts: in 7 of 10 rows the reasoning turns to what "pass" means (does it include the start, the change station, the last stop) from about half way and is still there at the cap. In 9 of 10 the right station is already written, at a median of about 35% of the 2,048 tokens. So yes, the prompt handicaps a reasoning model, and the page should say so.
- **The single change that would make it fairer:** the map, the question and "Answer with the station name only", marked as arm A is. My guess is 1,000 to 1,500 tokens a question, so all 100 could run in 8,700 s in place of 25 to 67. Cost: the new bar no longer differs from the published 54/36/10 bar by reasoning alone, the prompt is untested with no second chance, and the code plus registration is more than ten minutes. As a third arm from arm A's 4,300 s it costs all of arm A's 12 to 33 questions; split half and half, arm A falls to 6 to 16, under its floor. I don't make it a condition. If the author has 30 spare minutes, arm A's time is the place to take it from, because arm A at 8,192 tokens will probably run fewer than 25 questions and decide nothing anyway.
- **8,192 against 32,768.** At 23 tokens a second 32,768 is 1,400 s a question, 6 questions in the arm. 8,192 is the right trade. The page already says the card recommends more.
- **The decoding rule.** Fair. It looks only at finishing, and it prefers the card's precise setting. A hostile reader will say the card's "general" setting is the default for a non-coding task and its presence penalty is the card's own cure for loops. The answer: this task repeats station names exactly, and a presence penalty on already-used tokens works against that. The bar's label should say the setting was chosen on two practice questions by whether they finished.
- **One sample a question.** Acceptable. Three samples and a majority would cost two thirds of the questions. But at 30 to 60 questions the result cannot tell 90% from 80%: 27 right of 30 finished has a 95% interval of 74% to 97%. Print counts, and don't present the 90% line as a measured boundary.
- **The split.** Fine for the contested claim. Expect arm A to end under 25 questions.
- **In Qwen's favour already, and worth saying on the page:** each prompt carries only the four lines the question needs (about 2,200 characters), not the whole map, with a header saying the stops are in order of travel.

## Q2. What a fair but hostile expert says

- **Most right.** "The 54 was a reasoning-off strawman; a 4B model reads the map if you let it think." The registered rule (sentence off at 90% of finished, "catastrophically" off at a quarter or fewer wrong) is the right response. Three things would still overclaim: the reasoning-off bar shown first or larger than the reasoning-on bar; the page's worked examples, which show "Qwen with map" answering Times Sq-42 St on question 100 where the saved reasoning reached Canal St, unless they are labelled reasoning off; and the plural "models" for one model.
- **Most wrong.** "One prompt, one sample, a quarter of the card's length, a few dozen questions." The registered wording covers it if fix 2 is in, so that "wrong" means the wrong station and not a format slip. Check by hand whether the reasoning was right and the final line wrong.
- **Most unfinished.** "You capped it and gave it a prompt that sends it in circles. Unfinished is not 'cannot read'. Your own rows show the right answer inside the reasoning." This is the outcome in fix 3, where the registered rule leaves the page overclaiming.
- **Underclaim.** None that matters. If arm M is strong, the page is still entitled to say what the map arm cost (thousands of reasoning tokens a question, the right four lines handed over) and how many it still got wrong.

## Q3. Marking

See fix 2. The concrete shape for "correct and finished but marked unfinished" is `**Answer**: Canal St`. For "marked wrong" it is ``Answer: `Canal St` `` or any text after the answer line.

## Q4. Forecast for arm M

Of the questions that run: about 75% right, 20% unfinished, 5% wrong. So right on roughly 88% to 97% of the finished ones, with "catastrophically" coming off in nearly every finished-enough case and the 90% line a coin flip. Unfinished above 25%: about one in three with the precise setting, nearer one in two if the rule falls back to greedy. Questions run: 35 to 60 at 23 tokens a second, 18 to 30 if the game stays open.

Basis: reasoning on had the right station in 9 of these 10 questions where reasoning off was right on 4. The tenth, question 105, is Qwen arguing with the map's "northbound" label from wrong geography ("Bay Ridge is in Queens"); it was the looping row and was unfinished with reasoning off too. What the rerun really measures is whether the reasoning closes.

If Qwen reads the map well, the author should be ready to say, in this order: the earlier bar was reasoning off and the page said so; with reasoning on Qwen got N of M right from a prompt holding the four lines it needed, at about so many tokens and seconds a question; the sentence about reading the map is gone; and the post's claim is the one in its closing section, that the model holds the map as exact facts a sentence can change, with no map in the prompt. That claim never depended on stock Qwen failing with the map in front of it. Say the first two before anyone on Hacker News does.

Verdict: run after changes. (1) Close a game or re-base the budget on the practice rows' measured tokens a second. (2) Register the normalised answer-line count as the one that drives the page rules, strict beside it. (3) Register that an undecided arm M scopes "catastrophically bad" to reasoning off, and add the prompt sentence to what the page keeps.
