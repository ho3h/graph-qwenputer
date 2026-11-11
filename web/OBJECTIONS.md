# What people will say, and what answers it

Written 3 Nov, for Theo's launch post. Each row: the objection, the honest answer, the evidence, where the post handles it, and what's still open.

| # | Objection | Honest answer | Evidence | In the post | Still open |
|---|---|---|---|---|---|
| 1 | Isn't this just an external tool call? | On accuracy, yes: the tool ties it on every row. The work happens in the model's own layers | Tool tie, 900 rows; wrong map 0 of 600 (K3); zeroed chip layers (K2); 1,133,115 real-weights positions in lockstep on the fix's build so far | Body, FAQ | K1, K2 results |
| 2 | Why not all in the model? | Memory must change and weights can't during a run. A driver also loads memory and routes tokens | `rv/chat.py`; head check at printed tokens; K1 plain loop | Diagram 2, body, FAQ | K1 says how much of the driver is essential |
| 3 | Who cares? | Maybe few, today. Exact, inspectable machinery in a model is a research object | State returned word for word 33 of 33; replay on real weights | "So why bother?", FAQ | Nothing measures closures against weight editing |
| 4 | What are the practical uses? | None in production today. Stated plainly | About 1 minute and 5,300 tokens a question | "So why bother?" | Faster firmware or direct circuits, after launch |
| 5 | What are the implications? | Hedged: exact parts in models; monitors a model can't edit (Agrawal's argument); others building (qwenFS, qwenGPU) | Cited sources | "So why bother?" | Argument, no result |
| 6 | Rube Goldberg: 5,300 tokens to read a map | Yes, and we show it to scale | Dots figure, FAQ | Body, FAQ | qwenFS's direct reads suggest a cheaper route |
| 7 | It memorized New York, or you overfit | No training; Qwen alone, reasoning off, 10 of 600; wrong map 0 of 600 | `exam/results/after/` | Bars, FAQ | Blind city still sealed |
| 8 | You changed the test after seeing results | Yes, once, disclosed; frozen result stays first | `exam/REGISTRATION.md`, `R1.md`, repo hashes | "New York broke my first attempt", FAQ | Blind test of the fix |
| 9 | That's a simulator | Mostly, for machine exams; the edit exam ran whole on the real weights | 335,703; 795,589; query exam overnight | Body, FAQ, table header | Query exam running |
| 10 | It only copies a template; it'll fail on real language, and it does harm | New wordings 97 of 100, written by me; hard pool 84 on practice; wrong closes 14 of 30 shown as a game | `after/w/`, E1 | Game, body | Sealed pool unrun; shared-name closures running |

Also likely: "already done" (Neural Turing Machines, Percepta's WASM, Qwenputer, qwenFS are all credited or linkable); "can I run it" (no, model unreleased, answers checkable).
