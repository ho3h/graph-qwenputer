# T2 audit

**Turns I disagree with:** none. I re-scored all 30 from `rows/` with my own code. Every verdict matches, and all 42 firmware lines equal reflib. My spec, rule, examples and graphs didn't change across the run.

**My total: 24 of 30** (15 of 20 hard, 9 of 10 plain).

**Weakest pass:** C2 turn 3. Its first call is right, so my rule passes it, but 9 extra reads followed, the 12-call cap hit, and its reply is raw tool-call text. So 23 of 24 passes ended in an answer.

**Scorer, no row affected:** a listed call with no `direction` accepts `direction: in`. A listed call printing `NONE` only from earlier state fails, against "scored alone".

**Summary:** the numbers are right. Four fixes make it fair:
- Say C2 turn 3 counts as right and never replied.
- Qwen wrote `Valve 12b` and `Brunnich's guillemot`. The quoted spellings are the user's.
- "Indirect change 7 of 8" leaves out C3 turn 2, a missed write I didn't tag as indirect. Writes are 8 of 10, with 1 unreached.
- I wrote examples of the same kinds as the questions, so the by-kind rates aren't blind to wording.
