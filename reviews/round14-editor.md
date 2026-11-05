# Round 14: features edit

## 1. Throughline

As delivered: an exact computer can run inside a language model, and here is my audit of it.

Best: I put a machine that can't be wrong inside a language model, and the hard part was getting the model to listen to it.

That's already your ending, with twenty steps of near silence before it. Your data holds the beats: Qwen turned refusals into wrong answers, never passed on stop lines, and named wrong stations while the machine's line recorded the closure. Use them, so the push pays something off.

## 2. Structure

Steps 1 to 12 are right and the best thing here, except step 6, which explains your "still confusing". Running state, scratchpad, laptop, graph, my program and the driver land in one stop, with two different "small programs" a sentence apart. Split it: memory and map, then driver, with the picture building.

Steps 13 to 16 are the drama. Fold 17 into 16.

Steps 18 to 20 are the sag: each repeats step 11 at larger scale. Make them one toy, with the blackout as a button and the route picker inside.

Step 21 (wonder) then 24 (reversal) is the right order, and 24 is the right climax. Merge 22 and 23 to shorten the gap.

The ending works as a line and fails as a conclusion: "So why bother?" wanders off, and the last paragraph jumps back unattached.

To the README: Neural Turing Machines, the 8 raw refusals, the 23 conversations.

## 3. Ten weakest

1. "...overwrite one row of that scratchpad exactly, and that's all computer memory has to do."
   "A layer can overwrite one row of that state exactly, and somewhere you can write a thing and find it unchanged later is all computer memory is." Keep the laptop.
2. "...the driver, loads them at the start of each conversation and steers the tokens."
   "Here's the catch. The map isn't in the file you'd download. A script outside the model, the driver, loads it when a conversation starts and decides whether Qwen or the computer speaks next."
3. "...where a moment ago Qwen was at Union Station."
   "And that's right. On its own, this same model told you Union Station."
4. "one square lights up on the sign..."
   "The grid up top has a square for each of the 496 stops, and one has just lit."
5. "From here on I'll call the actual model the real weights..."
   "From here on, assume a result came from the simulator unless I say it ran on the real model." Then cut every "These ran on the simulator" and "real weights".
6. "So far nobody has had to understand a sentence."
   We just watched Qwen read the flood. "That test skipped Qwen. The exam put it back: Qwen read each question and wrote the query itself."
7. "There wasn't one wrong answer." and "Reader, I was not smug."
   "It got 147, and the machine refused the other 53. It never once named a wrong station." The joke needs setup: "After that table of perfect scores I'd got smug, and then I met New York's station names."
8. "Qwen's rows mark what it wrote, and the machine's rows mark the line it printed..."
   The map row is never introduced. "I also tried the obvious alternative: I pasted each question's lines into the prompt and let Qwen reason step by step. It got 54 right, and 36 of its misses were confident wrong stations. That's one prompt, so it may do better."
9. "Wrongly closes on a trick sentence", never defined.
   "A trick sentence is something like 'The newsstand at Lafayette Av has closed for good.' The station is fine. Qwen fell for 14 of 30 like that, and the machine obeyed."
10. "The computer's state lives in the model's own run, so it travels with that run..."
    "The machine's memory lives inside the model's run, so if you have the run you have the memory. A well-logged outside program could offer much the same, so I wouldn't lean on it."

## 4. Transitions

- 5 to 6: replace the "wake it up" tease with "But a computer with nothing in its memory can't help you yet."
- 17 to 18: "Those trips ran on a map that never changed. I chose the subway because it does."
- 23 to 24: "Those sentences were about the city. The last test was about the machine: would Qwen still believe it if I argued?"
- 24 to "So why bother?": "So the machine is exact, an ordinary tool is just as exact and far faster, and Qwen can still overrule what it's told. Which brings me back to the question I promised."
- Monitor to ending: "A watchdog only helps if something listens to it, and that's what I can't get past."

## 5. Machine or Theo

Machine: the clipped verdict closing nearly every step. "That's the price of working this way." "No weight changed, only the memory." "It did have help." One is a voice, and a dozen is a template.

Theo: "outrageously intelligent", "I'd distrust anyone who could", "Look at the second one." That voice thins out from step 13 to step 22, where it's needed most.

## 6. Cut too hard

- **147 against 47.** Text says 147 of 200, chart says 47 of 100, no bridge. "Half that exam was questions I'd generated with unique names. On New York's own 100, it got 47."
- **What refusals cost.** At step 14: "When Qwen read those refusals back, 25 of the 51 it didn't retry became wrong answers."
- **Why the table matters.** "Close a stop, and every trip through it should change while every other trip comes back exactly as it was."
- **The 100.** "All 100 use one wording, so Qwen is mostly copying a pattern."
- **Which machine.** Step 18 reveals that the machine you watched isn't the one step 13 tested. Say so at 13.
- **Generality.** Your north star is missing. In step 6: "It knows nothing about trains."
- **Your title's evidence** sits in a collapsed FAQ. Move to step 9: without the driver's routing the right answer still comes out, on all 6 trips, about five times slower.

**Hold before publishing.** Step 18 says "I ran the test again on that rule", but `exam/results/r6_all/READY` doesn't exist, so `web/build.py` prints its hardcoded 2,186 and 295,414, the old rule's figures. Step 20's "15 trips... all 5" comes from a partial file and reads as an error. I didn't trace 2,552.
