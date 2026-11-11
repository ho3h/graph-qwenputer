# Round 15 steel-man

Recounted from raw rows; toolkit rerun on a clean copy.

## 1. Strongest claim

A plain sentence changes an exact graph in a model's running state, and untrained layers answer from the changed graph: `r6_walk` and `z3c`, whole on the real model, 0 tokens different.

At 1440×900 the band fits the first screen. At 375×812 the claims start at 943 px, and the dek describes only a read. New second sentence:

> So I loaded New York's map into a computer that lives inside an LLM. Now a sentence can close a station or open a new line, and the computer finds the new route.

Right four, right order. Stronger proofs:

- Reroutes: "One whole conversation ran on the real model, and all 149,813 tokens matched the simulator. On 15 other trips, with the 11 layers on the simulator, Qwen closed the stop every time and all 15 new answers were right."
- Exact, append: "On the current build, all 342,992 exam calls matched a reference machine." (321,674 + 11,696 + 9,622.)

## 2. Stronger rows

- `r6_routes`, absent: "With 1 to 12 random stops closed, 1,719 routes between uniquely named stops matched the reference machine. 153 went a new way, 87 lost every path, and none used a closed stop. The run hit its time limit at 573 of 1,000 planned sets."
- Replacing "on every sample I compared": "Across every saved comparison, on six firmware builds, 4,979,984 real-model tokens matched the simulator, some conversations twice, and none differed. The check caught all 8 bits I flipped on purpose."
- `r6_walk`, after "The two fingerprints match.": "The route after the repair printed the same 10 steps in the same 39,584 tokens."

## 3. Hedges

- Too far: "The 15 trips ran on the simulator." Use: "In the 15 trips, Qwen ran on the real model and the 11 layers ran on the simulator." (`ran_on: executor`)
- Too far: the Question's "later versions" sentence. Use: "The later versions have not sat a frozen exam. The current version sat the whole machine exam with predictions written first: 321,674 calls, none different from the reference machine, and my forecast of changed answers missed. Qwen's trick-sentence exams ran on the earlier rule."
- Keep the rest: true limits.

## 4. "Why bother?"

The page concedes the tie three times and stops. The README's answer sits unheaded at line 295. New Question, also for launch post 5:

> **Why build the graph-qwenputer if an ordinary tool is faster?** For directions, use the ordinary tool. I can't name a production system that should use the graph-qwenputer. The graph-qwenputer tests a narrower question: can a model hold an exact part, with memory the model rewrites during its run, and can you check that part token by token? So far, yes. Qwen is the unsolved half: pushed, Qwen repeated my wrong station after the graph-qwenputer printed the right one, 10 times out of 10.

## 5. Toolkit

Fair on evidence. Not available yet: logged out at 16:15 EST, GitHub returned 404 and Hugging Face 401.

For me, 69 of 69 checks passed, and my own CSV ran 8 firmware calls agreeing with both references. T1's 16 answers replayed exactly. `ask` ran only on Theo's Mac, on his plain questions, with no reviewer.

The page never offers the toolkit. After "The map is just data", add: "You can load your own graph from a CSV file. Across packages, flights, an org chart and New York, Qwen wrote the right calls on 11 of 11 plain turns. I wrote the questions and examples."
