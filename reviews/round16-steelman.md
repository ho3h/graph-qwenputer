# Round 16 steel-man

Strongest case: one firmware hash met every machine prediction on maps opened after registration (commit 16:24:50, first draw 16:25:36, manifest hashes equal). 995,198 recounts.

## 1. Blind test: too quiet
296 of 300 sits only in a closed Question. Step 14 says "not a blind test" and never says one followed. New cell, same height at 1440×900:

> **Exact on sealed maps** On two maps sealed until my predictions were written, all 643,348 simulator calls matched a reference machine. On invented names, Qwen copied one template and the graph-qwenputer printed 296 of 300 right, 0 wrong. *(proof)* All 995,198 calls on this build matched. An ordinary tool gets the same answers in milliseconds.

Add to step 14: "The blind test came later: on a sealed map with invented names, all 100 shared-name starts printed the right answer."

On a phone, this cell starts at 1,183 px.

## 2. Toolkit: buried
24 of 30 sits at 27,055 of 28,305 px. T3 appears nowhere on the page, README or posts. Replace `newp`, same height:

> The map is just data: load your own graph from a CSV file. On a reviewer's own graphs and questions, Qwen wrote the right calls on 24 of 30 turns. Two small graphs of mine also ran whole on the real model, all 40,407 tokens matching the simulator.

## 3. Most harmful: "Did you change the test?"
314 words, 25 numbers, and "have not sat a frozen exam" beside "sat the whole machine exam".

> Once, for the exams. The first exam scored 147 of 200 against my prediction of 176 to 198, and the miss stands. After one fix, fitted to the refusals, all 300 printed answers were right, and that score is not blind. I later opened two sealed maps with predictions written first. All 643,348 simulator calls matched a reference machine. On invented names, the graph-qwenputer printed 296 of 300 right and refused 4 misspelled names. The questions copy one template.

Move "225 of 300" and the 40-of-40 sentence to the reliability Question; `check_figures.py` requires both.

## 4. Thread: post 7
Post 7 has no toolkit result. 279 characters with links:

> 7/ The map is just data: load your own graph from a CSV file. On a reviewer's own graphs and questions, Qwen wrote the right calls on 24 of 30 turns. Two small graphs ran whole on the real weights, 0 tokens different.

Move the driver and "public" sentences to post 6.

## Flags
- The reliability Question still has the pushback result.
- README line 191 says the current build "hasn't had a frozen exam".
- Logged out, GitHub returns 404 and Hugging Face 401.
