# Round 16: prose pass (Fable, 5 Nov)

Visible prose in `web/template.html` and the English strings in `web/build.py`. Headings, intro, quotes, numbers and claims untouched.

**Counts** (built page): 319 sentences, 59 of six words or fewer, before; 236 and 34 after. Words 3,901 to 3,841. `audit.py`: 0 hits.

**Passive kept:** "nothing was trained", "No server gets called" (no actor is the point), "could be compiled in", list fragments in the tech aside.

**Check:** 1 of 316,767 failed, "S2 on invented names": it wants "296 / 300" in `release/README.md`, gone since today's 10:21 README commit. Pre-existing; the page still says "296 of 300".

**Pairs** (* marks a meaning shift)
1. "While Qwen is talking, the computer stays out of the way." → "While Qwen talks, the CPU does nothing, because only the end of a query switches it on." *
2. "The map is not in the model file. A script outside the model, the driver, loads the map…" → "The map lives outside the model file. When a conversation starts, a script outside the model, which I call the driver, loads the map…"
3. "This model is Qwen 3.5. Each bar is…" → "The model is Qwen 3.5, and each bar is…"
4. "Qwen writes two calls. The first call closes the stop." → "Qwen writes two calls: the first closes the stop, which writes to…, and the second…"
5. "one square has just lit" → "the square for Saratoga Av has just lit" *
6. "A train that stops at a closed stop is cut off there." → "a closed stop cuts off any train that stops there" *
7. "No weight changed. Only the memory changed." → "with the weights untouched and only the memory changed."
8. "Told that a new line had opened" → "When I told Qwen that a new line had opened" *
9. "The two fingerprints match." → folded into the fingerprint sentence.
10. "I tested the driver's role on 6 trips. I removed…" → "I checked that on 6 trips by removing…"
