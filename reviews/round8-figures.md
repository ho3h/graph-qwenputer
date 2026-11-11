# Round 8: figure audit

Launch blocker: `gh repo view` says `subway-in-the-weights` is PRIVATE, so every repo link 404s.

## CONFIRMED errors, ranked

1. **Journeys: Atlantic Av transfer drawn via DeKalb Av.** Coney-Flushing, Inwood-Coney, Prospect Park-Van Cortlandt, Times Sq-Coney, both turns. White line and train run 0.8 km to DeKalb and back (`jc4`, `jc12`). True: @182-@183 is a 180 m transfer; DeKalb is in neither list nor machine line. `geoHop` tries a shared neighbour first. Fix: test transfers first, draw straight, add to the checker.
2. **Journeys: closed marker under the route.** `drawJ` marks before `ride`. Ring hidden on about 10 of 14 (`jc0`, `jc7`, `jc12`); labels cut ("Lexington Av/5/ St" `jc4`, "Alabama Av" `jc11`). Fix: draw the route first.
3. **MANHATTAN is printed on New Jersey** (`d-map`; every sampled point is in `near.json`). Fix: harbour, thin leader.
4. **"Bay Ridge" reads as a Staten Island stop.** Text spans the Narrows onto the SIR line. Fix: anchor right.
5. **Map labels "14 St" and "Atlantic Av" name other stops.** They mark @28 Union Sq and @181 Barclays; step 13's "14 St" are elsewhere, and "Atlantic Av" is @180 on the L. Fix: "Union Sq", "Barclays Ctr".
6. **T quote stops short.** Saved turn continues "Going northbound, its stops are Roosevelt Island, then Foxglove St, then Willow Gate, then Junius St." Without it Qwen seems to choose the route. Fix: quote whole; say "two made-up stations", which the page never does.
7. **Choice: machine line cut, "Ocean Pkwy > Brigh"** (`build.py` slices at 140). Fix: no slice.
8. **Dropdown says "1 Av" while W 4 St is closed** (`d-play`); 193 options are indistinguishable (six "Canal St"), each closing one platform. Fix: sync `ps.value`; append lines.
9. **Van Siclen Av: 1 moved, sentence shows no change** ("...New Lots Av > ...New Lots Av"), the only one of 427. Fix: show step counts.
10. **Deck tool call is tidied.** Saved text has line breaks inside each parameter (`demo/all.jsonl`). Fix: caption "line breaks tidied".
11. **Bullets "H", "GS", "FS".** GTFS `route_short_name` is S for all (`jc11`). Fix: display S.
12. **Step 8: fingerprint of "everything... its stops".** T row: sha stays b4b3c9dba00b20ea after both `add_node` calls. Fix: "its connections and closures".
13. **Blackout: "matched the first 600".** That run has no opening 600: tags are close, reopen, during, final. Final equals the file's base 600/600. Fix: "a fresh machine's 600", twice.
14. **Row "Qwen's written reply" shows my score.** Fix: "Reply listed every stop?"
15. **Tech box.** "Each result says which ran it": the 97 of 100 and bars don't. Upstream README line 6: the CPU also has Zba. Fix: label them; "RV32IM plus Zba".
16. **Cause disagrees.** Step 5: nonsense "because nothing told it to stop"; inside section: machine tokens through Qwen's layers. Fix: use the second.
17. **Diagram "loads the map"**; firmware too (PATH line 57). Fix: "loads firmware and map".

## Accurate, but will look wrong

- **Backtracks.** Mets, Coney-Flushing and Grand Central-Flushing ride 74 St > 69 St > 61 St > Junction Blvd, 180° at 61 St (`jc3`). Also `jc2`, `jc7`, Whitehall via Brooklyn (`jc8`), `jc11`, Neck Rd via Coney Island. All match the reference. Add to step 19: "Fewest stops by the map's rules, changes counted and time ignored, so some are routes nobody would ride."
- **Route crosses the closed stop.** Trains run through without stopping; step 7 says so, step 19 doesn't. Add a line.
- **168 St closed, route uses 168 St-Washington Hts, 44 m away** (`jc9`). Separate nodes; only A/C closed. Same for Lexington Av/59 St. Add to that line.
- **"24 steps" against 23 listed stops.** Machine counts changes; list merges same names. "5,890 machine steps" means tokens. Use "24 steps, changes included"; "machine tokens".
- **Fulton St: four rings for "five".** @318 and @320 are 24 m apart. Deck implies Fulton caused all 53. Add "two overlap"; deck "53 refused on shared names".
- **"Qwen: 425 Pennsylvania Av" reads as an address.** 425 is the handle, and strict marking fails it. Say so at step 5.
- **T northbound runs southeast**, hand-placed. From memory, not data: T is the MTA's planned Second Avenue line, in that teal. Use a neutral colour.
- **Saratoga Av: 0 of 600.** Correct, and the first stop readers try. Add: "The walkthrough's trip isn't one of the 600."

## Checked and right

- **Map:** 496 positions within 20 m of GTFS, names exact, 0 stops off land, neighbour land under the city. Classic MTA palette; the feed's `route_color` differs, and the checker compares only to its own constants.
- **Walkthrough:** stops, bullets, 5,890, 200, 22,479, fingerprints. Lit square is row 7, column 11, index 445.
- **Routes:** all 15 and closures match saved lines; right node marked.
- **Trip picker:** pins on each name's lowest handle.
- **Fulton, 14 St, Times Sq, 125 St:** stops, labels, counts.
- **Blackout:** 2,552 calls, counts match rows.
- **Close sentences:** 12 stops match rows, four at 0.
- **T:** other deck strings; 7 of 20 hit limits.
- **Bars, tables:** match PATH or rows.
- **Tech box:** 11 + 32 = 43 (`config.json`), 424 tensors identical, `exec/engine.c`.
- **Not verified:** October 29 and the HN quote; layer order; "0 of 900" and "five times" (round 6 only).

## What the checker can't see
Draw order, label placement, truncation, select state, wording. `hops()` passes a transfer without checking its drawing.
