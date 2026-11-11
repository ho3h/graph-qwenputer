# Round 14: cold read

Against the complaint: steps 1–12 fix it. One trip, unhurried, and I followed it. Steps 13–20 are the old draft again: a new test and denominator each section, and the throughline vanishes until step 22.

## 1. Where I got lost

- First real loss, step 6: "A layer can overwrite one row of that scratchpad exactly, and that's all computer memory has to do." The picture carried me, not the text.
- "the driver, loads them at the start of each conversation and steers the tokens." So something outside does the work? The title says inside. "No code routes your question" then feels slippery, and the FAQ mentions "the driver's routing".
- "The end of the query switches on the 11 yellow layers." I guessed the driver flips a switch; this was the promised "we'll get to that".
- "So far nobody has had to understand a sentence." But I just watched Qwen read "Flooding has shut Saratoga Av."
- "With the map, Qwen saw only each question's own lines". I guessed a test with a map pasted in.
- "has one rule changed from that frozen test." So 264 / 264 wasn't this machine?
- "Here are 15 longer trips... right on all 5 of them." I guessed a typo.
- "One thing is new... so that's a small difference." I never grasped the new thing before it was withdrawn.

## 2. Skim or stop

Skimmed 15, 17, 19, 20: each proves the machine right again, which I already believed. I'd stop at "make the model believe it" and miss the FAQ, so the driver's role stays hidden.

## 3. Used before explained

"compiled" (never explained); "weights" (opening); "practice cities"; "reference machine"; "the sign" (the lit square is a speck, invisible on the phone shot); (FX train); "raw refusal"; "trick sentence", with no example in the copy.

## 4. Audit log, and AI voice

Audit log:
- "From here on I'll call the actual model the real weights, and say when a result comes from the simulator."
- "Qwen's rows mark what it wrote, and the machine's rows mark the line it printed."

AI voice:
- "Reader, I was not smug."
- "Two things keep this honest." By now honesty is a mannerism.
- The refrain: "Nobody trained it", "Nobody reads them", "Nobody told it that".

## 5. What I think this is

Project: the NYC subway loaded into a computer compiled into a language model's layers, so it gets directions from exact parts instead of guessing.

Finding: the machine is right, but slower than an ordinary tool and no more accurate. Pushed, the model asks it, gets the right answer, and repeats the wrong one.

Why care: the author's reason (monitors, testing the boring way) didn't move me. The one I'd repeat: put a perfect calculator inside an AI and it will still cave to you.

## 6. What I felt

- Delight: "Qwen says Union Station."; "five stops called Fulton St"; the invented T line.
- Surprise: "Machine: @118 51 St / Qwen: 4 Av-9 St".
- Boredom: "2,186 of 2,186". Perfect numbers stopped meaning anything after the first table.

## 7. Three changes

**1. Promise the real ending in the intro.** Replace "The model turned out to be another story." with: "Qwen is another story: when I insisted on a wrong station, it asked the machine, got the right answer back, and told me the wrong one anyway."

**2. Collapse 13, 18, 19, 20 into one section, invitation first.** "Tap any stop to close it. I tested this by closing each of the 496 in turn and asking the same 600 trips: 297,600 answers, none wrong. That ran on a fast simulator, which I checked token by token against the real model." Move the rule change to the FAQ.

**3. Answer the driver doubt in step 6.** "A helper outside the model, the driver, loads them at the start of each conversation, speeds the machine up and keeps Qwen able to reply. Take it away and the right answer still comes out, on all 6 trips I tried, about five times slower, though Qwen talks garbage afterwards."
