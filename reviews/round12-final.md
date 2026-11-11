# Round 12: final audit, 4 Nov

`check_figures.py`: 3,247 of 3,247.

## BLOCKERS

1. **"DRAFT. Not released." is on the page.** `web/template.html` line 157. Delete and rebuild.

2. **`/og.png` doesn't exist** in `web/` or the build, so share cards break. Add it or cut the image tags.

3. **README run steps fail on a fresh Mac.** `tok/cexec.py` hardcodes Homebrew's LLVM clang, `numpy==2.5.4` needs Python 3.12, and `hf` arrives with the pip step that follows it. Replace from "You need the model" through the pip block:

   > You need a Mac with Apple silicon, Python 3.12 or later, Homebrew's LLVM (`brew install llvm`, which compiles the simulator on first run) and at least 24 GB of free disk. I've only run it on a 128 GB M5 Max. The model is at [link], 18.76 GB.
   >
   > ```bash
   > python3 -m venv .venv && source .venv/bin/activate
   > pip install -r requirements.txt
   > hf download hopski/graph-qwenputer --local-dir model
   > ```

   Confirm "24 GB" means disk; I found no measurement.

4. **`exam/bundle.sh` omits the new evidence,** so the README's r5 rows are absent and `check_figures.py` crashes in a scratch bundle. With the rows added it passes. Add:

   `copy $R/mini/r5 $A/z3b/all.jsonl $A/z3/all.jsonl $A/z3c/all.jsonl $A/z3_draw.json $A/round11 reviews/round11-critical.md reviews/round11-steelman.md reviews/round12-final.md`

5. **"walked 21 stops" is wrong:** 21 steps, 22 stops, 3 steps on the new line. Replace:

   > Qwen wrote the same query, and the machine printed a {{Z3STEPS}}-step route through the two stops Qwen had just added.

## Other fixes, ranked

1. `run.py` pins the MPS cap at 0.25, with no override. Qwen's layers are about 9 GB, so smaller Macs will probably run out (my estimate). Delete both `PYTORCH_MPS_*` settings.
2. `Z3RAN` in `build.py`, as only one conversation ran that way: "One of them, on the real weights, matched through its first two turns, 90,911 positions with none differing, and my time limit ran out before the final route."
3. After "3 of 3 such conversations.": "This was a later build with a route fix, described below."
4. `buildT` caption: "steps, across a line Qwen just wrote".
5. Stale FAQ: "and later built separate versions for writes, shared names and route cost."
6. README Cost line: "On the writes build, a long route after an added stop or link would take hours on the real weights; the route-fix build takes minutes. A route with a stop closed gets no fix: 817,464 tokens on a 14-stop chain."
7. `AFTER.md` lacks results for `r5_directed` and `r5_all`. It also says r5 isn't cited until r2's attack run is read; that has 8 rows, all equal.
8. README "every figure": say "main figures".
9. Pin `huggingface_hub==2.2.0`, the tested version.
10. `THIRD-PARTY.md`: note the Qwenputer copy in `vendor/`. README: explain "r4".
11. Launch: GitHub private, lacks `run.py`; Hugging Face 401; domain 404.

## Checked and right

Other figures; "Those ran Qwen on the real weights and the machine on the simulator"; `try.py` on Python 3.9; `walk.py`; requirements against imports; credit; licences. No stale claims.
