# Round 17: cold read as a casual reader

One pass, in order, page text only, as a daily ChatGPT user outside New York.

## 1. Where I got lost

Terms used before the page explains them:
- "Give Qwen a few stops": Qwen is named before the page says Qwen is a language model.
- "a real-world graph problem": I read "graph" as a chart. The definition comes 40 lines later.
- Summary band: "token", "simulator", "the 11 layers", "calls", "reference machine", "firmware", "sealed".
- "one token comes out": a token is never defined, so 6,279 tokens has no reference point.
- "only the end of a query switches it on": "query" comes three sections later, and "it" is unclear.
- Never introduced: "the question file", "my practice cities", "the exams", "trick sentences", "reviewer agent", "qwenFS".

Cryptic sentences:
- "A layer can also overwrite one row of the scratchpad exactly." Why does this matter?
- "the 11 layers signal when the computer owns the next token".
- "the wrong map gives 0 of 600 right answers." Which wrong map?

## 2. Arguments that do not follow

- "accuracy is not a reason to build the graph-qwenputer": the page never states the reason.
- "Runs inside the model" against "The map lives outside the model file", and "in front of Qwen" against "inside an LLM".
- "54 right and 36 wrong" leaves 10 unexplained. "84 of 100, with 9 wrong" leaves 7.
- "refused the other 53" for shared names, then "all 47 questions from the file with shared-name starts".
- "Qwen alone" scores 10 of 600, 1 of 100 and 0 of 100, and no line relates them.
- "all 300 printed answers were right" and "Qwen's written replies scored 225 of 300" are one exam. Only a collapsed question says so.
- The three set-ups (all real; Qwen real with the 11 layers simulated; all simulated) are never listed together.

## 3. Three sentences

- Built: the author put the New York subway map and a route-finding program into the memory of Qwenputer, a processor that sits inside the Qwen 3.5 language model as 11 extra layers.
- How: Qwen turns a sentence into a query, the end of the query switches on the 11 layers, the 11 layers compute one token at a time, and Qwen reads the printed answer.
- Why it matters: I cannot write this sentence. The page says an ordinary tool gives the same answers in milliseconds, and never says what working inside the model gains.

## 4. Order

The opening paragraph says what the thing is. The summary band then reports results in vocabulary the walk-through has not taught. From "This is a language model" to the reopened station the order works well. The driver section would read better after the first printed answer.

## 5. Top 12 fixes, ranked

1. Current: "...so accuracy is not a reason to build the graph-qwenputer."
Proposed: "Accuracy is therefore no reason to build the graph-qwenputer. I built the graph-qwenputer to see whether a real-world graph problem could live inside the model itself." The author should then say why that result matters.

2. Current: "...and one token comes out."
Proposed: add "A token is a word or a piece of a word."

3. Current (band): "...every token matched the simulator. On 15 other trips I chose, with the 11 layers on the simulator, all 15 new answers were right."
Proposed: "The largest tests ran on a simulator, which is a program that does what the 11 added layers do, much faster. One whole conversation ran on the real model, and every token from the real model matched the simulator. On 15 other trips that I chose, Qwen ran on the real model and the 11 added layers ran on the simulator, and all 15 new answers were right."

4. Current: "Give Qwen a few stops to follow..." and "...the billions of numbers the model is made of."
Proposed: "Give a language model called Qwen 3.5 a few stops to follow on the New York subway, and Qwen will tell you..." Then: "The weights are the billions of numbers that the model is made of."

5. Current: "...to see whether a real-world graph problem could live inside the model itself."
Proposed: "A graph is a list of things and the connections between the things, and I wanted to see whether a real-world graph problem could live inside the model itself."

6. Current: "The map lives outside the model file."
Proposed: "The model file does not contain the map. When a conversation starts, the scratchpad is empty, and a script outside the model, which I call the driver, loads the map into the scratchpad."

7. Current: "...because only the end of a query switches it on."
Proposed: "While Qwen talks, the CPU does nothing. The CPU switches on only when Qwen finishes writing a query, which is a request that Qwen writes in a fixed format."

8. Current (first use in the body): "...and every token matched the simulator."
Proposed: "A simulator is a program that does what the 11 layers do, much faster, and every token from the real model matched the simulator."

9. Current: "...all 643,348 calls on two maps I kept sealed until my predictions were written matched a reference machine..."
Proposed: "I kept two maps sealed until I had written my predictions. On a simulator, the graph-qwenputer answered 643,348 calls on the two sealed maps, and every answer matched a reference machine that runs the same firmware." The author should define "call" and "firmware" once.

10. Current: "...and in a sentence a shared name like 125 St gets a refusal."
Proposed: "When you tap a stop, the page closes the stop by the stop's number, and Qwen is not involved. When a sentence names a stop that shares a name with other stops, such as 125 St, the graph-qwenputer refuses."

11. Current: "First I asked for a route from Prospect Park to Tottenville."
Proposed: "First I asked for a route from Prospect Park to Tottenville, which is on Staten Island." (Author to confirm.)

12. Current: "...Qwen named two real stations on 0 of 10 tries..."
Proposed: "I asked Qwen 10 times where a new line should go, and Qwen named two real stations on 0 of the 10 tries. On 4 of the 10 tries Qwen reached a limit before Qwen gave an answer: 3 tries reached the token limit and 1 try reached the call limit."
