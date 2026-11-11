# Round 18 pre-run steel-man

Nothing ran on the GPU and no model was loaded. Letters in B stand for counts.

## A. The arms
The pair is right: with the published bars, the pair makes a two-by-two of map and reasoning on the same 100 questions.

**One change: run arm M first with a deadline of 7,500 s (hard stop 7,600 s, gate 05:52), then arm A with 4,500 s (4,600 s, gate 06:42).** The total stays 12,200 s. An arm finishes 100 questions in 6,000 s only when the mean stays under about 1,400 new tokens. Arm M decides the opening's wording, and a near-zero arm A reads the same from 60 questions.

**Do not change** the prompts, the cap, the question order, greedy decoding or the one attempt. `Qwen.forward` returns only the greedy token, so sampling would be new, untested code.

Add to `score_think.py` before rows exist: arm M's generous count on the `Answer:` line, as in `score_mapped.py`, because the numbered list names the right station whenever Qwen rides past that station; a paired table against the reasoning-off rows; and a count of unfinished rows whose last 64 token ids occur earlier in the row.

## B. Sentences
**Arm A low, arm M moderate.** "With Qwen's reasoning turned on and a limit of 2,048 new tokens, Qwen alone got a of 100 right, so reasoning does not supply the map. With the map lines in the prompt, Qwen got m right, against 54 with reasoning off, and Qwen still named a wrong station on w trips of 2 to 6 stops."

**Arm A low, arm M 90 or more.** "With reasoning on and the map lines in the prompt, Qwen got m of 100 right, so Qwen reads a pasted map well when Qwen reasons. The graph-qwenputer's result is the exact map in the running memory and the sentences that change the map, and that result does not depend on Qwen reading a map badly."

**Arm A above the prediction.** "I predicted that Qwen alone would get at most 12 of 100 right with reasoning on, and Qwen got a, so my prediction was wrong. With reasoning on, Qwen knows more of New York's subway than the Union Station answer suggests."

**Many unfinished.** "Qwen did not finish u of the 100 questions inside my limit of 2,048 new tokens, so this run does not settle what Qwen does with reasoning on. On the f questions that Qwen finished, Qwen got r right and w wrong. In L of the u unfinished questions, Qwen's reasoning was repeating an earlier passage when the limit came."

## C. Predictions and the rule
Arm M's range is 36 wide and starts one above 54, so nearly any gain is a hit. Add a prediction for wrong answers among finished questions.

Ninety is the right bar for removing the claim and the wrong only bar for "catastrophically": 85 right, 3 wrong and 12 unfinished would keep the word. Right on 90% of finished questions: the sentence comes off. Wrong on a quarter or fewer: "catastrophically" comes off and the sentence gives the wrong count. More than 25 unfinished: the run decides no wording. Arm A's rule becomes 12% of questions run.

## D. Keep whatever happens
"I tested one model, Qwen 3.5 4B, with one prompt for each test, greedy decoding and a limit of 2,048 new tokens, where Qwen's model card recommends sampled decoding and up to 32,768 tokens. A larger model, another prompt or a longer limit might do better, and I tested none of them."
