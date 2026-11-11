# Round 6: cold read

Read as a marketer who uses ChatGPT and has never heard of this. I read the template's text and the `scenes` captions. I did not see it rendered, and the contents of `{{DATA}}` (trip chips, tool-choice chips, the close-it game sentences) weren't available, so I can't judge those lines. I can only judge the idea of them.

## 1. After the header and intro

The headline works. "Closed every station" and "got the model to build itself a new line" are fun and I'd keep going.

What I think it is: someone trained or tricked a chatbot into knowing the subway. I don't know what "compiled a working computer into a language model's weights" means, and I assume it's a stunt. I care a bit, mostly because the writer admits a stranger called it a Rube Goldberg machine and he couldn't answer. That honesty is the hook.

Two things snag me in the intro:

- "Multiplication felt like a weak test." What multiplication? Nobody mentioned any. It reads like a paragraph went missing.
- "Weights" and "Qwen 3.5" are never explained. I don't get told Qwen is a chatbot-type model. Hacker News points mean nothing to me.

## 2. Step by step

**Step 1.** Fine. "475 of the 496 stops in my map file, with Staten Island left off" is fussy for the first thing you tell me, but harmless. "The computer is inside an AI model" I take on faith.

**Step 2.** Best explanation in the post. The question is concrete and "it's confident anyway" is funny. Token is defined. Thank you.

**Step 3. First place I got lost.** "Tool call" is used as if I know it. "The closing tag is itself a signal to 11 extra layers sitting in front of Qwen's own." I reread this twice. What tag? What's a layer? "In front of" how? The caption shows `<tool_call>` and the word `chase`, which is never explained.

**Step 4.** "RISC-V" gets rescued by "the kind of processor you could buy". "Compiled into numbers" I half follow. "Nobody trained it" lands. "On the real weights it takes about a minute": real as opposed to what? Nothing has told me there's a fake version. "Real weights" appears again and again before the simulator is explained at step 9.

**Step 5.** "I ran it with nothing outside choosing tokens, only a loop taking the model's top pick." Reread, still unsure why it matters. I can tell it's the proof of something. 3 of 3 sounds small next to everything else.

**Step 6. Second loss, and the worst one.** The heading says "The map isn't in the weights." The title says the map is inside the model. So is it inside or not? "Running state", "Gated DeltaNet layers", "overwrite exactly one row" and "exact RAM" arrive together and I skim. I keep only "every byte matched". The caption's `sha` means nothing to me.

**Step 7.** Clear again. A closure moves the trip one stop on. "No weight changed, and no other answer has any reason to move" is a nice line, once you've got the idea.

**Step 8.** `b4b3c9dba00b20ea` twice is a good visual if I'm told it's a fingerprint of the whole machine. I'm not. "Try doing that by editing a model's weights" is a punchline to a joke I wasn't told. Nobody has said people edit weights, or why it goes wrong.

**Step 9.** Tapping stations: great. Then 2,186 of 2,186 and 295,414 of 295,414, then "our simulator", which is the first I hear of it. "Second reference machine" is unexplained.

**Step 10.** Good, simple, visual.

**Step 11.** The payoff. I smile at "Cinder Park and Larkmoor Sq". "Graph store" and "typed connections" go past me, but "It knows nothing about trains" gets the point across. This is where I'd tell a friend about it.

**Below the steps, where I'd stop.**

- "It got New York right": the paragraph with "That's about 0.3% of the frozen exam: about 40 of the 11,750 circuit gates reached were never compared" is where I start skimming. I can't tell what "that" refers to.
- "New York then broke my first attempt" pulls me back, because it's a story. "Reader, I was not smug" is good. The 14 St figure is clear.
- "Frozen sitting" in the bar chart: I have to work out what this means.
- The bold "A normal tool outside the model... tied the machine" is the most trust-building sentence on the page, and I nearly missed it.
- **The paragraph right after it ("After the fix, it also got all 100 new...") is where I'd actually leave.** Six separate scores, four denominators, "an internal number stuck to the name", and "it never once said a trip had stopped early" about a problem I never heard of.
- If I stayed, "Nobody tells Qwen" is clear and fun.
- "Its judgment is the weak part" is a good idea with a table I can't parse: "Reopens it (frozen: 16 conversations ended on a refused start)", "Of 15 tricks on the route, the answer moves".
- The paragraph after that table is a list of small failures with no through-line.
- "What's inside the model" has the diagram I needed at step 6. Then "ends the turn in print mode", which is never explained.
- The graph store limits paragraph is pure chore.
- "So why bother?" I'd read this if I got here, and many won't.

**Unexplained terms, in order:** weights, Qwen, CPU, Hacker News, tool call, closing tag, layers, `chase`, compiler, real weights (versus what), Gated DeltaNet, running state, RAM, `sha`, byte-identical, simulator, reference machine, graph store, typed connections, frozen, sitting, circuit gates, firmware, driver, print mode, sandbox, differentiable memory.

**A number that wobbles:** "about 6,000" tokens in step 4, 6,338 in the captions, "about 5,000" twice later. It may be one trip versus an average, but I notice and it isn't explained.

## 3. Fun and chore

**Fun:** the map moving with the trip. Tapping a closure. The blackout. Building the T. The 14 St figure. "Reader, I was not smug." Repeating the start station beating Qwen alone (18 versus 10) is the funniest fact in the post and it's hidden in a collapsed FAQ. The admission "I'd distrust anyone who could". The close-it game, in principle.

**Chore:** every paragraph where scores pile up with qualifiers. The simulator audit. The graph store limits. The judgment table. The FAQ's second round of the same points.

## 4. My two sentences

He took a downloadable AI model, left it untouched, and attached a tiny real computer made out of the same kind of numbers, with the subway map in that computer's memory, so the model can write a query and get an exact answer that updates when stations close or a line gets added. It might matter because it shows exact, checkable machinery can live inside a fuzzy model, though he says himself an ordinary tool gets the same answers far faster and nobody should use this today.

I can say the first sentence in my own words. The second is me repeating him. I don't actually know why it matters.

## 5. What I didn't believe

- **The perfect scores as evidence.** After a while I think: it's a computer, so of course it gets the right answer. 295,414 of 295,414 is impressive only if I understand why a computer inside a model might fail. Nobody tells me.
- **"So why bother?" reason one.** "You can read it, compare it and restore it word for word." So can a normal database, I assume. Reason three, "no server and no sandbox", is followed by a list of things you still need, including an 18.8 GB file. These feel like reaches.
- **"Here, nothing catches it" and "Nothing routes your question."** Later I learn a driver outside the model "routes tokens" and "ends the turn", and without it Qwen's reply is garbage. It's disclosed, so I don't feel lied to, but I feel the early steps oversold, and step 5's "the answer came out of the model's own layers" now needs an asterisk.
- **"Inside an AI model"** in the title, once I've read "only the top box is the model file" and "you have an empty machine".
- **"I froze the build", "I ran it".** The footer says Claude Code ran the exams and reviewers were agents. I'd also assumed "a reviewer's short script" meant a person. Not a dealbreaker, but it should be clear sooner.
- **Taking it on trust.** The model isn't released and the page says DRAFT. I can't run it.

I did believe the failures. Every miss made me trust the rest more.

## 6. Five smallest edits

Facts in these need the author's check against the sources. I haven't seen them.

**1. Intro lead.** Replace the first paragraph with:

> On October 29, Divyansh Agrawal's <a href="https://divagr.com/blog/qwenputer">Qwenputer</a> took off on Hacker News: a working CPU, the chip at the heart of any computer, written directly into the weights of a language model called Qwen 3.5. Weights are the huge pile of numbers an AI model is made of. His demo multiplied numbers. Some people were delighted. One asked if it was "yet another rube goldberg machine", and then asked why. That's a good question, and I couldn't answer it.

**2. Step 3.** Replace both paragraphs with:

> Qwen reads the question and writes a query, in the format chatbots use to ask for outside help, like a web search. That's called a tool call. Normally a program outside the model would run it and hand back the result.
>
> Here, no outside program runs it. The end of the query switches on 11 extra layers, stacks of calculation that sit in front of Qwen's own.

**3. Step 4.** Replace "It really is that lopsided, and on the real weights it takes about a minute." with:

> It really is that lopsided. On the actual model, which I'll call the real weights, it takes about a minute. For the biggest tests I use a faster simulator, and I'll say which is which.

**4. Step 6.** Replace the first paragraph with:

> The weights hold the computer, and they never change. The map, and whatever the computer is working on, sit in its memory, which exists only while the model runs. So the model holds the map the way a laptop holds an open file. Agrawal's trick was noticing that some of Qwen's layers can overwrite exactly one row of that running memory at a time, which is what a computer's memory needs.

**5. "So why bother?"** Replace "compiled weights make exact, inspectable parts inside a model you can study, including monitors a model can't quietly edit." with:

> compiled weights can put exact parts inside a model, parts you can inspect and that behave the same way every time. One example is a monitor, a small watchdog inside the model that the model can't quietly rewrite. That's the first reason in this post that made me want to know more.

Runner-up: replace "Try doing that by editing a model's weights." with a sentence saying what goes wrong when people do, if that can be sourced. It's the only place the post could tell me why exact writes are hard.

## 7. What to cut

- **"After the fix, it also got all 100..." paragraph.** Keep one sentence: "Ten new ways of asking, which I wrote myself, got 97 of 100." Link the rest.
- **"That's about 0.3% of the frozen exam: about 40 of the 11,750 circuit gates reached were never compared."** Move to the repo.
- **"though it isn't an unseen map: it comes from my earlier work and shaped the first design"** and **"on a missed prediction, which is a generous reading of my own rule"**. Honest, but too inside. Keep them in the repo, or as one plain FAQ line.
- **Graph store limits paragraph.** One sentence is enough: "It holds about 1,000 stops, and nothing survives the conversation."
- **The paragraph under the judgment table.** Keep "It closed nothing unasked on plain questions: 0 of 900" and the sentence on wrong closes.
- **Judgment table.** Cut the "Reopens" and "Of 15 tricks" rows, or say them in words.
- **FAQ "Who cares? What is it for?"** It repeats "So why bother?".
- **Neural Turing Machines line.** "Yes, about 5,000 tokens of one per question" is the better whole answer.
- **704 points and 146 comments.**

Move, don't cut: the "What's inside the model" diagram goes straight after the steps, or better, into step 6. The start-station fact (18 versus Qwen's 10) comes out of the FAQ and up into step 2.
