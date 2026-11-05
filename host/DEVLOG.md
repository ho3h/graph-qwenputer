# X2.10 host-tool baseline: dev log

Development only. Nothing here is a gate measurement, and nothing reads data/heldout/.

## 2026-11-01
- 12:30-13:00 ET. Harness written (tools, model, harness, score, run, report, spelling, test/). Offline tests pass:
  parsing, response bytes equal to the chat template's own rendering (text and token ids, thinking on and off),
  scoring, the held-out guard. Eight tools, then ten after SPEC added `link` and `unlink` (MAX_LEGS 16).
- 12:47 ET. CPU smoke test, one tiny question, eager: answered, 2 calls, correct, 615 s (262 s prefill on a busy CPU;
  CPU is unusable for this). Qwen's first call spelled the label "Eastgate station", got NONE, then retried "Eastgate".
- 13:10 ET. The Mac panicked (another stream's CPU test ran out of RAM). Host files survived.
- New rules from the lead: every model process under tools/memguard.py --limit-gib 28; MPS watermarks 0.25 / 0.2.
  If memguard kills a run, shrink the job; the limit is not raised.
- reflib is now 894d2c50... (weights through closed nodes are minimal). Tiny gold regenerated with it.
- 14:22 ET. Choices so far: a question's `setup` runs on the host before the prompt (its text says "After close ...");
  tiny questions use `gold_setup` instead, so Qwen makes those calls itself. Each record replays the canonical call to
  flag stale gold. Scoring ignores a gold label found only inside a longer label ("Falcon Av" in "Falcon Av/14 St").
  Worker launched on MPS under memguard with a 3-question probe (out/dev1/worker.log).
- 14:26 ET. Probe on MPS: model loads in 98 s; 5-13 s per normal question; footprint about 10.9 GiB, driver 9.84 GiB.
  Finding: tiny q17 eager copied the response format into an argument ("@4 Harbor Point"), which the tool answers with
  NONE, and looped to the 12-call cap; sdpa wrote "@4" and answered. First difference at generated token 22.
- 14:37 ET. Main finding so far: after any response, Qwen tends to write node arguments as "@4 Harbor Point", copying the
  response line. SPEC section 4 accepts "@4" or "Harbor Point" but not both, so the tool answers NONE and Qwen wanders,
  often to the 12-call cap. It also appends "station" to names ("Eastgate station", "Central station"). The harness
  reports this as measured; the tool is unchanged. Whether to accept "@h label" is a SPEC decision for the lead.
- 15:13 ET. dev1 (reflib 894d2c50..., before `@h label`): 50 questions under eager and sdpa. Eager 26/49 scored and 18 hit
  the cap; sdpa 27/49 and 20 hit the cap. 320 of 685 node arguments were "@h label"; 172-182 tool results per arm were NONE.
  Identical transcripts 28/50 (56%), same score 49/50. Saved in out/dev1/ (report.txt, spelling.txt).
- 15:15 ET. Lead: SPEC section 4 and reflib now accept "@h label" when the label matches node h; "station" stays
  unnormalised and is counted. dev2 re-runs the same 50 questions. dev2-repeat re-runs 7 of them unchanged, to check
  that two runs of one implementation agree on MPS. dev3-clear is the dev arm with node arguments described as "use the
  exact name or the @handle". Three "stale gold" flags in dev1 were false: tiny's replay ignored gold_setup (fixed).
- 15:51 ET. dev2 (reflib 2a406e3e..., accepts "@h label"): eager 42/49 scored, 5 at the cap; sdpa 41/49, 6 at the cap.
  Identical transcripts 29/50 (58%), same score 49/50. Saved in out/dev2/report.txt.
- 15:52 ET. dev2-repeat: 14 of 14 repeated runs (7 questions, each implementation) were token-identical on MPS, so the
  eager/sdpa differences come from the implementation, not from run-to-run noise. Remaining dev2 failures: two-leg rides
  done with `follow` and no transfer, the "Otaki" spelling, and MULTI loops.
- 16:13 ET. dev3-clear (same reflib, node arguments described as "use the exact name or the @handle"): eager 42/49 with 3 at
  the cap and 1 over the token budget; sdpa 42/49 with 4 at the cap. Same accuracy as dev2, fewer calls (2.9 per question
  against 3.7), 13.0 s against 17.9 s per run, identical transcripts 38/50 (76%), same score 50/50. Node arguments ending in
  "station": 23 per implementation in dev1 and dev2, 12 and 11 in dev3-clear. Worker peak 12.16 GiB under the 28 GiB guard;
  no kills. Saved in out/dev3-clear/. Stopped the worker; the 50 questions are spent for this dev check.
