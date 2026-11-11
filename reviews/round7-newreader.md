# Round 7: new reader

I judged the tap map and game from stills and source, without clicking them.

**My one sentence:** "Someone compiled a CPU into an AI model, this guy loaded the NYC subway into its memory so the model computes routes inside itself, and he tested it hard enough to admit a normal tool scores the same." I can't say why it's interesting without reaching "So why bother?".

**I'd show a friend:** the blackout, the closure rerouting the trip, the trick-sentence game.

## Ranked fixes

1. **Intro: the question goes unanswered for 2,500 words.** The page is about 2,900 words, or 12 minutes. I have three. After "I couldn't answer it", add: "I still can't name a production system that should use this. I can show you what an exact part inside a model does, where it breaks, and why the weak link is the model's judgment."

2. **Scene 3: I stopped believing.** "Here, no outside program runs it" is followed, far below the map, by a driver that "reads the machine's next token off its layers". It feels like a gotcha. In scene 6, add: "A small program outside the model loads that memory and routes tokens. I'll show exactly what it does."

3. **Scenes 14 to 18: I got bored.** The T line, the dek's best promise, starts about 1,850 words in. Scenes 14 and 17 run about 1,400px on one map state. Split 14 at the chart. Move scene 18 to Fair questions.

4. **Scenes 5 and 6: I got lost.** Scene 5: "To check, I loaded the memory, then ran a bare loop that always prints the token the model rates most likely." Move "Agrawal's trick" and "with the tokens supplied and every machine token checked" below the map, intact.

5. **Words I didn't understand.** Swaps:
   - "byte-identical" to "exactly the same"
   - "direct calls, with no Qwen" to "I sent these straight to the machine, with no Qwen"
   - "frozen sitting" to "first sitting, before the fix"
   - deck "sha" to "fingerprint"
   - "stored graph" (scene 8): define graph here, as the definition waits until scene 19

   Also undefined: "positions", "firmware", "scratch memory".

6. **Scenes 14 and 16: sentences that defeat me.**
   - "on all 11 trips that stopped early, told to answer with the station name only, it never said so": stopped by what? Author should name the cause.
   - "Of 15 tricks on the route, the answer moves | 6" becomes "Trick sentences about a stop on my route: the answer moved | 6 of 15".
   - Color "14 / 30" as bad; rows 1 and 2 are high-is-good.
   - Move "21 of the 11,589 circuit gates" to the simulator Fair question.

7. **Scene 19 and dek: jargon at the payoff.** Replace "With a map that already had an empty T relation and worked turns showing how" with "I set it up first: the map already had an empty slot called T, and the prompt had worked examples showing how." The dek's "got the model to build itself a new line" oversells that setup. Try "and, with worked examples, got the model to add a new line."

8. **Visual bugs.**
   - Journey, desktop: the route runs off the right edge and "Mets-Willets Poin" clips. `frame()` shifting the view by `W*.12` is a likely cause.
   - Scenes 13 and 14: SVG text renders near 10px in the 380px column, smaller on phone. Enlarge the labels.

## Also

- **Scene 10:** "Tap any stop" means aiming at packed Manhattan dots with no zoom. Show the stop name on hover.
- **Scene 14:** name "Trip 1" to "Trip 6" by destination. Cut "Hover or tap a bar"; counts are printed.
- **Phone:** the map takes 58% of the screen, so long scenes read through a slot. "Qwen alone: Broadway-Lafay" clips in Trips.

## Keep

"Just repeating the start station would score 18." The 5,392 counter. Scene 8's failed reopen. "Reader, I was not smug." The bold "tied the machine" line, which earned my trust. The game. The map. The inside/outside diagram, the clearest thing on the page; consider moving it up to scene 6.
