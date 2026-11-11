# Round 17: every changed passage, live page against the local revision

The live page is https://subway.outofcontext.io as deployed on 5 Nov. The revision is `web/index.html`, not deployed. Reasons are in `round17-casual.md`, `round17-expert.md`, `round17-critical.md` and `round17-steelman.md`.


## Opening

**Live:** Give Qwen a few stops to follow on the New York subway and Qwen will tell you with total confidence that you've arrived somewhere you haven't. In October, Divyansh Agrawal published Qwenputer: a working computer written directly into the weights of a language model called Qwen 3.5, the billions of numbers the model is made of.

**New:** Give a language model called Qwen 3.5 a few stops to follow on the New York subway, and Qwen will tell you with total confidence that you've arrived somewhere you haven't. In October, Divyansh Agrawal published Qwenputer: a working computer written directly into Qwen's weights, the billions of numbers that the model is made of.

**Live:** (nothing)

**New:** A graph is a list of things and the connections between them, and a subway map is a graph.


## Qwenputer put a CPU inside a language model. The graph-qwenputer adds a graph that the CPU can read and rewrite while the model runs.

**Live:** One whole conversation ran on the real model, and every token matched the simulator. On 15 other trips I chose, with the 11 layers on the simulator, all 15 new answers were right.

**New:** One whole conversation ran on the real model, and every token matched a simulator of the 11 added layers. On 15 other trips that I chose, with the 11 added layers on the simulator, all 15 new answers were right.

**Live:** - **Exact on sealed maps** On a simulator, all 643,348 calls on two maps I kept sealed until my predictions were written matched a reference machine running the same firmware.

**New:** - **Exact on sealed maps** I kept two maps sealed until I had written my predictions. On a simulator, all 643,348 calls on the two sealed maps matched a reference machine that runs the same firmware.

**Live:** On the invented-name map, Qwen alone got 0 of 100, and Qwen with the graph-qwenputer printed 296 of 300 right.

**New:** On the sealed map with invented names, Qwen alone got 0 of 100, and Qwen with the graph-qwenputer printed 296 of 300 right, with the 11 added layers on the simulator.


## This is a language model.

**Live:** (nothing)

**New:** A token is a word or a piece of a word.


## Now put a computer in front of Qwen.

**Live:** The 11 yellow bars are what Agrawal added to Qwen: a RISC-V CPU, the kind of processor you could buy off the shelf. While Qwen talks, the CPU does nothing, because only the end of a query switches it on.

**New:** The 11 yellow bars are layers that Agrawal added to the model, in front of Qwen's 32 layers. Together, the 11 layers are a computer: a RISC-V CPU, the kind of processor you could buy off the shelf. While Qwen talks, the computer does nothing. The computer works only when Qwen asks for an answer.


## Then put the map in the computer's memory.

**Live:** Layers of Qwen's type keep a running state, a kind of scratchpad that they update with each token, so the model can keep track of the text it has already read. A layer can also overwrite one row of the scratchpad exactly. The subway map goes into the scratchpad as a graph, a list of stops and the connections between them, and a small program of mine goes in beside the graph to read it and change it.

**New:** Layers of Qwen's type keep a running memory, a kind of scratchpad that the layers update with each token, so the model can keep track of the text it has already read. A layer can also overwrite one row of the running memory exactly, so the computer can use the running memory to store data. The subway map goes into the running memory as a graph, a list of stops and the connections between them. A small program of mine, called the firmware, goes in beside the graph, and the program can read the graph and change it.


## One part stays outside the model.

**Live:** The map lives outside the model file. When a conversation starts, a script outside the model, which I call the driver, loads the map into the scratchpad. The driver has one more job while Qwen and the computer take turns: the 11 layers signal when the computer owns the next token, and the driver reads that signal and keeps the computer's tokens out of Qwen's layers. Start from the model file alone and the computer's memory is empty.

**New:** The model file does not contain the map. The running memory starts empty in every conversation, so a script outside the model, which I call the driver, loads the map and my program into the running memory when a conversation starts. The driver has one more job. Qwen and the computer take turns to produce tokens, and the 11 layers signal when the next token belongs to the computer. The driver reads that signal and keeps the computer's tokens out of Qwen's layers.


## This time Qwen writes a query.

**Live:** With the graph-qwenputer in place, Qwen no longer has to know the answer, because Qwen's job is to turn your sentence into a query that names where you start and the two legs of the trip. The format is a tool call, the way chatbots ask for outside help, and Qwen knows how to write one because the prompt shows it a few worked examples.

**New:** With the graph-qwenputer in place, Qwen no longer has to know the answer. Qwen only has to turn your sentence into a query, and the query names where you start and the two legs of the trip. Qwen writes the query as a tool call, which is the format that chatbots use to ask for outside help. Qwen knows how to write a tool call because the prompt shows Qwen a few worked examples.


## The graph-qwenputer wakes up, and works in tokens.

**Live:** The tokens are CPU instructions and CPU results, and nobody needs to read them.

**New:** The tokens are the computer's instructions and results, and nobody needs to read them.


## The graph-qwenputer prints the answer, and Qwen reads it.

**Live:** ## Graph-qwenputer prints the answer, and Qwen reads the answer.

**New:** ## The graph-qwenputer prints the answer, and Qwen reads it.


## Flooding shuts Saratoga Av.

**Live:** Qwen writes two calls: the first closes the stop, which writes to the graph-qwenputer's memory, and the second asks for the route again.

**New:** Qwen writes two tool calls. The first tool call closes the stop, which changes the graph in the running memory. The second tool call asks for the route again.

**Live:** Saratoga Av is on the 3, the line you were riding, and a closed stop cuts off any train that stops there.

**New:** Saratoga Av is on the 3, the line you were riding. A train that stops at a closed stop cannot pass the closed stop, and the 3 is now cut in two at Saratoga Av.


## Reopen the station, and the map comes back exactly.

**Live:** I took a fingerprint of the graph-qwenputer's record of edits, which covers closures, added connections and removed connections, before the flood and again after the repair, and the two fingerprints match.

**New:** Before the flood and again after the repair, I took a fingerprint of the graph-qwenputer's record of edits. The record covers closures, added connections and removed connections, and the two fingerprints match.

**Live:** The whole conversation ran on the real model, start to finish, and every token matched the simulator.

**New:** The whole conversation ran on the real model, start to finish. Every token matched a simulator, which is a program that does what the 11 layers do, much faster.


## The graph-qwenputer gets all 100 two-train trips right.

**Live:** When I pasted the relevant lines of the map into Qwen's prompt and let Qwen reason step by step, Qwen got 54 right and 36 wrong, though I tried only one prompt, so Qwen might do better with another.

**New:** When I pasted the relevant lines of the map into Qwen's prompt and asked Qwen to list each stop before answering, Qwen got 54 right and 36 wrong, and did not finish the other 10 within my limit of 1,024 new tokens. Qwen's reasoning stayed off for that test too, and I tried only one prompt, so Qwen might do better with another setup.

**Live:** The blind test came later: on a sealed map with invented names, all 47 questions from the file with shared-name starts printed the right answer.

**New:** The blind test came later, on a sealed map with invented names. Of the 100 two-train questions in that map's question file, 47 start at a shared name, and the graph-qwenputer printed the right answer on all 47.

**Live:** With ten new ways of asking that I wrote, the score was 97 of 100, and a harder set of wordings, on my practice cities, scored 84 of 100, with 9 wrong. The real model takes minutes per question, and up to about an hour for a route from a shared name, so the graph-qwenputer's tests ran on a simulator, a program that does what the 11 layers do, much faster. I compared the simulator with the real model, token by token, on New York's own queries, and all 335,703 tokens matched.

**New:** With ten new ways of asking that I wrote, the score was 97 of 100. A harder set of wordings, on the invented cities that I used for practice, scored 84 of 100, with 9 wrong and 7 refused. The real model takes minutes per question, and up to about an hour for a route from a shared name, so most of the graph-qwenputer's tests ran on the simulator. I compared the simulator with the real model, token by token. The fixed version answered these 100 questions whole on the real model, as part of an exam of 300 questions, and all 1,640,598 tokens of that exam matched the simulator.


## Now close any stop you like.

**Live:** The stops you tap close by number, with no Qwen involved, and in a sentence a shared name like 125 St gets a refusal.

**New:** When you tap a stop, the page closes that stop by its number, and Qwen plays no part. If you named the stop in a sentence instead, and several stops share the name, as 125 St does, the graph-qwenputer would refuse.

**Live:** A second CPU, built separately and running the same firmware, agreed on every call, and a separate Python library gave the same answers. You saw the rule in the flood: a closed stop cuts off any train that stops there, while an express train that skips the stop still runs. An earlier version let a train run through a closed stop, so your trip ended one stop later, and since that rule does not help someone with a destination, I changed the rule and ran the whole test again.

**New:** A reference machine agreed on every call. The reference machine is a second, separately built CPU that runs the same firmware. A separate Python library also gave the same answers. You saw the rule in the flood: a train that stops at a closed stop cannot pass the closed stop, while an express train that skips the stop still runs. An earlier version let a train run through a closed stop, so a trip that counted stops ended one stop later. That rule does not help a person who needs to reach a destination, so after I read a draft of this post, I changed the rule and ran the whole test again.

**Live:** Pick one of the 15 longer trips below, which I chose before I ran any of them, then shut a stop on the route and watch the new route go around the closed stop.

**New:** Pick one of the 15 longer trips below, which I chose before I ran any of them. Then press the closure sentence under the trip, and watch the new route go around the closed stop.


## Qwen can now build new train lines.

**Live:** First I asked for a route from Prospect Park to Tottenville.

**New:** First I asked for a route from Prospect Park, in Brooklyn, to Tottenville, on Staten Island.

**Live:** When I asked where a new line should go, Qwen named two real stations on 0 of 10 tries, and on 4 of those tries Qwen hit a limit first: 3 token limits and 1 call limit.

**New:** I asked Qwen 10 times where a new line should go, and Qwen named two real stations on 0 of 10 tries. On 4 of the 10 tries, Qwen hit a limit before Qwen answered: 3 token limits and 1 call limit.


## Q: Isn't the graph-qwenputer just a tool call?

**Live:** On the real model, no outside program calculates the answer, and the map reads back byte for byte from the model's running state.

**New:** On the real model, no outside program calculates the answer, and the map reads back byte for byte from the running memory.


## Q: Why isn't all of the graph-qwenputer in the model?

**Live:** The computer is in the model file, and the map and the program live in the model's running state.

**New:** The computer is in the model file, and the map and the program live in the running memory.

**Live:** A smaller outside part looks possible, because the qwenFS chat loop decodes tokens and stops, a qwenFS runtime pages files in, and qwenFS already has Qwen writing files and links.

**New:** A smaller outside part looks possible. qwenFS is another project that compiles a part into Qwen 3.5's weights, and qwenFS puts a file system in the model. The qwenFS chat loop decodes tokens and stops, a qwenFS runtime loads a file into memory when Qwen reads the file, and qwenFS already has Qwen writing files and links.


## Q: Did Qwen just memorize New York?

**Live:** No training happened, and Qwen's 32 layers are bit-identical. Alone, Qwen got 10 of 600, and with the map pasted in and step-by-step reasoning, Qwen got 54 of 100, with 36 wrong. On the simulator, the wrong map gives 0 of 600 right answers.

**New:** I trained nothing. Qwen's 32 layers still hold Qwen's released weights, in wider layers that make room for the computer, and the technical notes below give the exact comparison. Alone, Qwen got 10 of 600. With the map pasted in, I asked Qwen to list each stop before answering, and Qwen got 54 of 100 right, got 36 wrong and did not finish 10. On the simulator, with an invented city's map loaded, the graph-qwenputer got 0 of New York's 600 questions right.


## Q: Did you change the test after seeing the results?

**Live:** I changed the graph-qwenputer once for the exams, and I say so.

**New:** I changed the graph-qwenputer once in response to an exam result, and I say so.

**Live:** Later versions added writes, shared names, cheaper routes and blocking.

**New:** Later versions added writes, routes from stops that share a name, routes that take fewer tokens, and the closure rule that you saw in the flood. I changed the closure rule after I read a draft of this post, and I ran the closure exam again. I predicted 2,100 to 2,300 changed answers, and 2,395 changed.

**Live:** (nothing)

**New:** I stopped that run at 244 of 300 questions to free the Mac, and the 56 questions that did not run all start at a shared name.


## Q: Do the results come from the real model or a simulator?

**Live:** The largest tests ran on a simulator, where all 995,198 machine exam calls on the current version matched a reference machine.

**New:** The largest tests are machine exams, which send calls straight to the graph-qwenputer with no Qwen. The machine exams ran on a simulator, where all 995,198 calls on the current version matched a reference machine that runs the same firmware. The 643,348 calls on the sealed maps are part of that total.

**Live:** A short script by a reviewer agent shares no code with this project and reproduces the graph-qwenputer's answers from the spec, though the reviewer agent is the same family of model that wrote the rest.

**New:** A short script by a reviewer agent shares no code with this project. The script rechecks 24,600 trip answers and 500 routes of the first two versions from the spec, under the earlier closure rule, though the reviewer agent is the same family of model that wrote the rest.


## Q: Does the graph-qwenputer make Qwen reliable?

**Live:** On the current version, with Qwen on the real model and the 11 layers on the simulator, Qwen closed the right stop 40 times out of 40 and reopened the stop 35 times out of 40, but wrongly closed a stop 13 times out of 30 on trick sentences.

**New:** On the current version, with Qwen on the real model and the 11 layers on the simulator, Qwen closed the right stop 40 times out of 40 and reopened the stop 35 times out of 40, but wrongly closed a stop 13 times out of 30 on trick sentences, such as "The newsstand at Lafayette Av has closed for good".


## Q: Can I run the graph-qwenputer?

**Live:** (nothing)

**New:** With the --whole option, the run script runs the 11 layers on the real model too.


## From Qwenputer

**Live:** (nothing)

**New:** - Qwen's 32 layers, widened from 2,560 to 3,968 dimensions. I checked the published model against Qwen's release: 360 of the 424 tensors in Qwen's layers match bit for bit in Qwen's own dimensions. The other 64 are normalization gains, and all 64 equal Qwenputer's rescale for the wider model exactly. Qwenputer also adds columns that are designed to keep Qwen's layers quiet on the computer's tokens.


## Real calls, from conversations on the real weights

**Live:** The map, questions, saved rows, reviews, spec and code. Track from MTA data, shorelines from NYC Open Data and the US Census. Not affiliated with the MTA.

**New:** The repo has the map, questions, saved rows, reviews, spec and code. The track comes from MTA data, and the shorelines come from NYC Open Data and the US Census. This project is not affiliated with the MTA.


37 passages changed. The diagram label "Qwen's 32 layers, bit-identical" is now "Qwen's 32 layers, not retrained", and the chart label "Qwen given the map, reasoning step by step" is now "Qwen given the map, listing each stop, reasoning off".
