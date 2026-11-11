# Round 17 steel-man

Bare line numbers: `release/README.md`.

## A. Closing section, after "Qwen decides when to call the tool"

**V1. "A language model can hold exact facts, and a sentence can change those facts."**

> For directions, use an ordinary tool, which gives the same answers in milliseconds. I built the graph-qwenputer to find out whether a language model can hold facts exactly and change those facts when a person says so. Qwen alone gave confident wrong answers, and Qwen's weights cannot change while Qwen runs. With the graph-qwenputer, the running memory held all 496 stops exactly, and a plain sentence closed a stop or added a line, with nothing trained. Across 496 closures on a simulator, all 2,395 answers that should change did change, and all 295,205 other answers stayed the same. The graph-qwenputer is slow, Qwen's judgment is still the weak part, and a small script still loads the memory.

Evidence: 208-209, 226; `exam/results/after/map_out/result.json` (real model, after a closure: 52,519 bytes read back, 0 differ).

**V2. "The subway is the proof, and the graph-qwenputer takes any graph."**

> The same model file runs any graph within the limits, up to 1,024 nodes, from a CSV file, with nothing trained for the new graph. On three graphs that a reviewer agent wrote before any run, all 42 answers from the graph-qwenputer were right, and Qwen wrote the right calls on 24 of 30 turns. The graph-qwenputer is slow, Qwen's judgment is the weak part, and a small script still loads the memory. I published the toolkit so that other people can test what an exact part inside a model is good for.

Evidence: 45, 213.

**V3. "An exact part can sit beside the learned part of a model."**

> Qwen's 32 trained layers named Union Station. The 11 added layers are the same type of layer with weights that a compiler wrote, and with my graph program the 11 layers held the map and found the routes. All 995,198 calls on a simulator matched a reference machine. Agrawal suggests uses such as a monitor that the model cannot switch off, and I have not built one. The graph-qwenputer is slow, Qwen's judgment is still the weak part, and a small script still loads the memory.

Evidence: Qwenputer README 11, 89; Agrawal's write-up, "Beyond arithmetic".

**Pick: V1.** V1 answers with Theo's own addition, a memory that a sentence rewrites, in numbers the reader has already met. V3 rests on Agrawal's layers and an unbuilt use. V2 fits the top of the technical section.

## B. Last sentence for "Isn't the graph-qwenputer just a tool call?"

> The result therefore shows something that a call to an outside tool cannot show: a language model's own layers and running memory can hold a 496-stop map exactly, search the map, and change the map when a sentence says so, with nothing trained.

## C. Undersold

**1. Qwen's layers.** `tok/results/r17_stock_tensors.json` (`not_exact: []`) supports more. After the 360:

> The other 64 tensors are normalization gains, and all 64 equal Qwenputer's rescale of the released values exactly, so the check accounts for every value in Qwen's own dimensions. Agrawal measured the ordinary text predictions of his Qwenputer model against base Qwen, and he reports a KL difference of 6e-4 against a noise floor of 5e-4. My additions changed none of Qwen's 424 tensors in Agrawal's model.

Do not use MMLU 71.9 against 71.7: Qwenputer's README gives it for the CHIP-8 model (its lines 39, 117), and the RISC-V figure is the KL (its line 188). `exam/AFTER.md:409` repeats it. No text check of the published model is saved; the vendored `rv/textcheck.py` would supply one.

**2. Qwen's writes.** The page reports 3 of 3. Line 242 and `exam/results/after/lines2/line_score.json` hold more. Add:

> On an earlier version, with a sentence that listed the stops in order, Qwen added the new stops in 20 of 20 conversations, linked the line in 19 and removed the line when told in 19, and 12 of the 20 conversations ran whole on the real model.

**3. Band, sealed maps.** The calls also equaled the separate Python library's answers (`exam/results/s1_*_score.json`, `AFTER.md:380`). Append: "and every answer also matched a separate Python library."

## D. Hedges past the evidence

- "…so do not take the conversation as typical." Replace: "I chose the trip and the sentences for this post. In the tests below, Qwen closed the right stop in 40 of 40 conversations and reopened the stop in 35 of 40."
- Band: "routes the tokens" implies that the answer needs routing. Without routing, 6 of 6 answers were right (182). Use "keeps the computer's tokens out of Qwen's layers".
- The page concedes the faster tool four times. Twice is enough.

## E. Opening

Every baseline is Qwen 3.5 4B with reasoning off (226-227), so the general claim has no row, and "catastrophically bad at reading the map" overstates 54 of 100. Use:

> A language model called Qwen 3.5 gets lost on the subway, even with the map in its prompt.

> And Qwen is very bad at this task: from memory Qwen got 10 of 600 trips right, and with the map pasted into the prompt Qwen still named a wrong station on 36 of 100 trips.

To keep "Large language models", run the file's 100 two-train questions with no map on one current frontier model with reasoning turned on.
