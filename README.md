# Graph Qwenputer

A graph computer inside a language model. The model can read and write an exact graph from inside its own run. The computer is compiled into the model's weights, and the graph lives in its running state, loaded when a conversation starts and gone when it ends. The graph code is firmware on that computer, using [Qwenputer](https://github.com/divagr18/qwenputer) by Divyansh Agrawal, which supplied the computer and the model calling tools that the weights answer. New here is the graph: typed, directed edges, reads and writes, up to 1,024 nodes. The model writes a query in plain tool-call format, the layers run it, and the answer comes back as ordinary tokens.

No training is involved. Qwen's 32 layers keep Qwen's released weights: Qwenputer widens each layer to make room for the computer, rescales the layer's normalization to match, and adds columns that are designed to keep Qwen's layers quiet on the computer's tokens. An ordinary tool gets the same answers in milliseconds, where this takes minutes. It's a working example of exact parts inside a model, tested in the open, including the misses.

New York's subway is the worked example and the test bed, with 496 nodes, 1,761 edges and 59 relations. The graph can be anything. [The launch post](https://subway.outofcontext.io) explains the idea through the subway, for anyone. This page is the working detail.

**What you can do today:** load your own graph, run it on the real firmware without a GPU, ask Qwen about it in the model, check the published answers without trusting my code, and read the predictions, results and reviews.

## Build with it

Make a graph from a CSV file, check it, and query it. These three steps need only Python 3.9:

```bash
python3 gq.py import examples/packages.csv -o packages.graph.json
python3 gq.py check packages.graph.json
python3 gq.py try packages.graph.json path app libc
```
```
packages.graph.json: 13 nodes, 15 edges, 1 relation.
packages.graph.json: 13 nodes, 15 edges, 1 relation. The file is valid.
To test the fit in the real firmware's memory: gq.py check --firmware --model DIR GRAPH
4 steps: @0 app > @2 auth > @5 crypto > @9 bignum > @12 libc
```

Then run the same query on the real firmware, with no GPU and no model weights. This step needs Python 3.12, 3.13 or 3.14 and Homebrew's LLVM (`brew install llvm`), and it downloads three small files. The pinned torch has no build for Python 3.15 yet, and I ran this on 3.14:

```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
hf download hopski/graph-qwenputer chipformer.json config.json tokenizer.json --local-dir model
python3 gq.py sim packages.graph.json --model model path app libc
```

Then ask Qwen. Qwen's layers run on the real weights, and the simulator runs the 11 added layers. Add `--whole` to run those layers on the real weights too, at about 60 machine tokens a second. This step downloads the 18.8 GB model and needs a Mac with Apple silicon:

```bash
hf download hopski/graph-qwenputer --local-dir model
python3 gq.py ask packages.graph.json --model model --examples examples/packages.examples.json --tools neighbours,path,close,add_node,link "What does web depend on?"
```

I ran these commands from a clean copy on three small graphs and New York, 11 turns in all. Qwen wrote the right call on all 11 by my reading, and all 16 firmware answers matched the reference library. I wrote the questions and examples, so that shows the path works.

For a harder test, a reviewer agent wrote its own graphs, a water network, a food web and a company register, with 30 turns, 20 of them hard, and a scoring rule, all before any run. By its rule, which scores calls and not replies, Qwen wrote the right calls on 24 of 30, and all 42 firmware answers matched the reference library. 23 of those 24 ended in a reply. The misses were names written differently from the graph, a pronoun read wrongly, a missed write, and one conversation that spent its 12 calls looping. The reviewer wrote the worked examples in the same kinds as the questions, so these rates aren't blind to the kind of wording. Two of my small graphs also ran whole on the real weights through this path, all 40,407 tokens matching the simulator.

[docs/TOOLKIT.md](docs/TOOLKIT.md) is the full guide: the CSV format, the firmware's limits, worked examples for your own domain, the parts you can swap, and how to rebuild the firmware. `python3 toolkit/test_toolkit.py` tests your setup.

## Run it in the model

You need a Mac with Apple silicon, Python 3.12 to 3.14, Homebrew's LLVM (`brew install llvm`, which compiles the simulator on first run) and 19 GB of disk. A run peaked at about 21 GB of memory on a 128 GB M5 Max, the only machine I've run it on. The model is at [hopski/graph-qwenputer](https://huggingface.co/hopski/graph-qwenputer).

```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
hf download hopski/graph-qwenputer --local-dir model
```
```bash
python3 run.py --model model --graph examples/team.graph.json "What's the route with the fewest stops from Dana to Kofi?"
```
```
You: What's the route with the fewest stops from Dana to Kofi?
  Machine: path {"from": "Dana", "to": "Kofi"} -> 4 steps: @3 Dana > @1 Ben > @0 Ana > @2 Chidi > @5 Kofi
Qwen: Dana, Ben, Ana, Chidi, Kofi
```

Each argument is a turn, and writes last for that conversation. `run.py` keeps Qwen's layers on the model and runs the 11 added layers on the C simulator, because that takes seconds where the real weights take minutes.

## Try it without the model

You need Python 3.9 or later and nothing else. Here's a small org chart:

```bash
python3 try.py --graph examples/team.graph.json path Dana Kofi
```
```
4 steps: @3 Dana > @1 Ben > @0 Ana > @2 Chidi > @5 Kofi
```

Edits last for one session, so pipe several calls, one a line, with arguments split by `|`:

```bash
printf 'add_node | Mira\nlink | Mira | reports_to | Ana\nneighbours | Ana | reports_to | in\n' | python3 try.py --graph examples/team.graph.json
```
```
added @6 Mira
linked @6 Mira > reports_to > @0 Ana
@1 Ben
@2 Chidi
@6 Mira
```

`try.py` runs `lib/reflib.py`, the Python reference the machine in the weights is checked against. On `data/heldout/nyc/nyc.graph.json` it reproduces all 43 calls of the first saved journey run exactly. The reference has no memory limits, so it accepts graphs and links the machine would refuse. Other known differences are in `SPEC.md`.

## The subway example

With no `--graph`, `try.py` loads New York, with closed stops blocking:

```bash
python3 try.py path "Bedford Av" "WTC Cortlandt"
```
```
7 steps: @210 Bedford Av > @0 1 Av > @87 3 Av > @29 14 St-Union Sq > @128 6 Av > @25 14 St > @253 Chambers St > @480 WTC Cortlandt
```

Closing a stop blocks it, so a route has to go around. The default map, `exam/items/nyc_b.graph.json`, works this way:

```bash
printf 'path | Bowling Green | Pennsylvania Av\nclose | Saratoga Av\npath | Bowling Green | Pennsylvania Av\nreopen | Saratoga Av\n' | python3 try.py
```
```
10 steps: @223 Bowling Green > @220 Borough Hall > @401 Nevins St > @181 Atlantic Av-Barclays Ctr > @312 Franklin Av-Medgar Evers College > @276 Crown Hts-Utica Av > @462 Sutter Av-Rutland Rd > @445 Saratoga Av > @440 Rockaway Av > @361 Junius St > @425 Pennsylvania Av
closed @445 Saratoga Av
14 steps: @223 Bowling Green > @220 Borough Hall > @274 Court St > @357 Jay St-MetroTech > @356 Jay St-MetroTech > @345 Hoyt-Schermerhorn Sts > @412 Nostrand Av > @471 Utica Av > @230 Broadway Junction > @232 Broadway Junction > @180 Atlantic Av > @461 Sutter Av > @377 Livonia Av > @361 Junius St > @425 Pennsylvania Av
reopened @445 Saratoga Av
```

The earlier exams used `data/heldout/nyc/nyc.graph.json`, where a closed stop is one a train runs through without stopping, so a count of stops simply ends one stop further on. The only difference between the two files, apart from an empty T line, is the `splice` list.

## Use your own graph

The quickest route is `gq.py import`, described above. A graph file is JSON:

```json
{"format": "x210-graph/1", "name": "team", "domain": "org",
 "nodes": [{"label": "Ana", "prop": 0, "src": "Ana"},
           {"label": "Ben", "prop": 0, "src": "Ben"}],
 "relations": ["reports_to", "manages"],
 "edges": [[1, 0, 0, 0]],
 "splice": [], "change": null, "meta": {}}
```

Each edge is `[from, relation, to, weight]`, where from, relation and to are positions in their lists. Edges are directed, a node's handle is its position in `nodes`, and labels may repeat. `python3 try.py relations` lists a graph's relations. `splice` lists the relations a closed node is passed through, so leave it empty if a closed node should block, and `change` names the relation used to change between legs. `python3 gq.py check` tests a file against the firmware's limits. [SPEC.md](SPEC.md) has the full contract.

## Operations

| Kind | Call | Example result |
|---|---|---|
| Read | `find name` | `AMBIGUOUS 5: @316 Fulton St \| @317 Fulton St \| …` |
| Read | `follow node relation steps` | `@h label`, or a line saying where it stopped |
| Read | `chase start legs` | `@425 Pennsylvania Av` |
| Read | `neighbours node relation [direction]` | one `@h label` a line |
| Read | `path from to` | `7 steps: @210 Bedford Av > …` |
| Read | `cheapest from to` | `cost c: @h label > …` |
| Write | `close node`, `reopen node` | `closed @445 Saratoga Av` |
| Write | `add_node name` | `added @496 Foxglove St` |
| Write | `link from relation to [weight]`, `unlink from relation to` | `linked @a label > relation > @b label` |

`add_node` exists on the writes build and the two builds after it, route fix and blocking, described below. Writes live in the running state and end with the conversation.

**Capacity, measured on the simulator:** it holds 1,024 nodes and about 6,880 edges with 9-byte names, takes 16 new stops and 256 added connections before `FULL`, and accepts names up to 31 bytes. A relation's name has to exist when the graph loads. The longest possible trip, 1,023 hops, took 360,976 tokens. On the writes build, one added stop or link made a `path` cost 13 to 36 times more, even on the loaded map: 2,697,045 tokens over 49 stops. The route-fix build brings that to 83,354. Across a chain of 12 new stops it takes 53,680, against 3,520,286. Rows: `exam/results/mini/r2/r2_cost.jsonl`, `exam/results/mini/r5/r5_cost.jsonl`.

## How it works

```
 The model file, fixed
 ┌──────────────────────┐  ┌──────────────────────────────────┐
 │ Qwen's 32 layers     │  │ 11 added layers                  │
 │ not retrained        │  │ a RISC-V CPU, never trained      │
 └──────────▲───────────┘  └───────────────▲──────────────────┘
            │                              │ reads and writes
            │ prompt       ┌───────────────▼──────────────────┐
            │              │ Running memory, per conversation │
            │              │ firmware, map, closed stops      │
            │              └───────────────▲──────────────────┘
            │                              │ loads firmware and map
 ┌──────────┴──────────────────────────────┴──────────────────┐
 │ Driver, outside the model: offers the tool, routes tokens  │
 └────────────────────────────────────────────────────────────┘
```

1. Qwen reads a question and writes a query in tool-call format.
2. The end of the query switches on the 11 layers. They execute the firmware, and each step of that work is a token. The walkthrough trip takes 6,279 of them on the current build, about two minutes on the real weights with nothing else running.
3. The machine prints the result as ordinary tokens, and Qwen reads them as if a tool had replied.

**From Qwenputer:** an RV32IM CPU with Zba, compiled into 11 layers added to Qwen3.5-4B. 256 KB of code ROM, 128 KB of read-only data and 32 KB of RAM, all in Gated DeltaNet state. Qwen calling a tool that the weights answer (`calc`), and on a branch, file tools in the same layers.

**New here:** the graph firmware (`t8/fw/`), the tools above, 85 added exit units so answers print as ordinary tokens, a reference machine and a C simulator to check it all against, and the exams. The simulator's source is `exec/engine.c`.

**What's outside the model.** The weights hold the computer, and they can't hold closures, because they don't change while a model runs. A small driver injects firmware and map into running state after the prompt, offers the tool, and normally reads the machine's tokens off its layers and keeps them out of Qwen's. Start from the weights alone and you have an empty machine.

The 11 layers signal when the computer owns the next token, and the driver reads the signal. I also ran it with no driver routing: memory loaded, then a bare loop taking the model's top token, with stop tokens off. It printed the right answer on 3 of 3 read trips and 3 of 3 trips with a closure, about five times slower. It ran through the layer modules, with a token cap set from the known stream. Qwen's reply afterwards was garbage, probably because the machine's tokens went through its layers.

## Five builds

| Build | Firmware | What changed |
|---|---|---|
| Frozen | `t8/fw/build_writes/writes.elf` | The build I froze before opening New York |
| Fixed | `t8/fw/build_r1/writes.elf` | One allowed revision: a line in the query can pick between stops that share a name |
| Route fix | `t8/fw/build_r5/writes.elf` | On the writes build, adding a stop or a link made every later route expensive. This keeps the fast search at stops no write touched, and reads edited stops once. It printed the same lines on my 400 write sequences and 14 routes, apart from one route the writes build couldn't finish. A route with a stop closed gets none of this, and routes with no writes cost 6 to 10% more. It hasn't had a frozen exam |
| Blocking | `t8/fw/build_r6/writes.elf`, with `exam/items/nyc_b.graph.json` | The current build. A train that stops at a closed stop is cut off there, and a route has to go around. An express train that skips the stop still runs. The rule comes from the map's empty `splice` list, and one firmware patch keeps those routes cheap. Results are in `exam/AFTER.md` under r6. Its blind test is the two sealed maps, below |
| Writes | `t8/fw/build_r2/writes.elf` | `add_node`, and a name counts as one station when its platforms connect. It hasn't had a frozen exam |

## Results, on the subway graph unless marked

"Simulator" is a C program checked against the real weights on samples. "Real weights" is the 18.8 GB model itself. "Stock Qwen" is Qwen3.5-4B without the added layers. Saved rows are in `exam/results/`, and `PATH.md` says how to read each one.

**The machine alone, no Qwen**

| Test | Build | Ran on | Result |
|---|---|---|---|
| Routes between sampled pairs | Frozen | Simulator | 500 / 500 |
| 20 closures: answers that should change | Frozen | Simulator | 264 / 264 |
| 20 closures: answers that should stay the same | Frozen | Simulator | 11,736 / 11,736 |
| Each of 496 stops closed: should change | Fixed | Simulator and reference | 2,186 / 2,186 |
| Each of 496 stops closed: should stay the same | Fixed | Simulator and reference | 295,414 / 295,414 |
| Close and reopen all 496 on one machine | Fixed | Simulator and reference | 2,552 calls right |
| Each of 496 stops closed: should change | Blocking | Simulator and reference | 2,395 / 2,395 |
| Each of 496 stops closed: should stay the same | Blocking | Simulator and reference | 295,205 / 295,205 |
| Close and reopen all 496 on one machine | Blocking | Simulator and reference | 2,552 calls right |
| A test aimed at the new operations, again | Blocking | Simulator and reference machine | 11,696 calls, 0 differences. The reference library differs on 24 `link` calls past the 256-edge limit, because the library has no such limit |
| Routes with 1 to 12 random stops closed, then all reopened | Blocking | Simulator and reference | 1,000 sets, 16,442 calls, 0 differences. Of 3,000 routes with stops closed, 307 went a new way, 147 lost every path, and none used a closed stop |
| Chains, rings, stars, trees, grids, scale-free, to 1,024 nodes | Blocking | Simulator and reference | 2,038 calls, 0 differences. The edit table in this test is void: see "Predictions that missed" |
| Non-subway graphs through `gq.py ask --whole`: packages and flights, 8 turns | Blocking | Whole on the real weights | 40,407 positions, 0 differ |
| Chains, rings, stars, trees, grids, scale-free, to 1,024 nodes | Fixed | Simulator and reference | 0 differences |
| The whole machine exam above, again, which doesn't touch the new operations | Writes | Simulator and reference | 321,674 calls, 0 differences |
| Random calls | Writes | Simulator and reference | 42,996 calls, 0 differences. Few reached the new operations: no `unlink` succeeded and only 9 `reopen`s did |
| A test aimed at the new operations | Writes | Simulator and reference machine | 11,760 calls, 0 differences. `unlink` 2,145 of 2,145, `FULL` in all 8 fills, 100 routes across added stops |

**Is the simulator honest?** Compared with the real weights: 335,703 positions on New York's own calls, plus 795,589 on the whole edit exam, 1,640,598 on the whole 300-question exam, 366,169 on the journeys, 22,479 on the earlier walkthrough and 149,813 on the current one. 0 differ, and it caught 8 of 8 bits flipped on purpose. 250 reserved token ids differ between simulator and weights, and the exams reject them. On the fixed build, 21 of the 11,589 circuit gates reached have never been compared.

**With Qwen writing the queries**

| Test | Build | Ran on | Result |
|---|---|---|---|
| Qwen alone, no map, reasoning off, 600 questions | None | Stock Qwen | 10 right. Repeating the start station scores 18 |
| Qwen given the map and asked to list each stop before answering, reasoning off, 100 questions | None | Stock Qwen | 54 right, 36 wrong, 10 unfinished at 1,024 new tokens |
| Qwen given the map and the question as written, reasoning on, one sample a question at temperature 0.6, the first 28 of the 100 questions | None | Stock Qwen | 26 right, 0 wrong, 2 unfinished at 8,192 new tokens. Reasoning off scored 16, 10 and 2 on the same 28 |
| Qwen alone, no map, the question as written, reasoning on, one sample a question at temperature 0.6, the first 7 of the 100 questions | None | Stock Qwen | 0 right, 0 wrong, 7 unfinished at 8,192 new tokens. Too few questions to decide anything |
| First exam, 200 questions | Frozen | Simulator, with real-weight samples | 147 right, 0 wrong, 53 refused. **I predicted 176 to 198 and missed** |
| The exam's 300 questions, printed line: 200 re-scored after the fix, 100 new that can't be refused | Fixed | Simulator, then whole on the real weights | 300 / 300 |
| The same 300, Qwen's written reply | Fixed | Simulator | 225 strict, 286 generous |
| Ten new wordings I wrote, 100 questions | Fixed | Simulator | 97 right, 1 clean wrong |
| Closes the right station | Fixed | Real weights | 40 / 40 |
| Reopens it | Fixed | Real weights | 33 / 40 |
| Wrongly closes on a trick sentence | Fixed | Real weights | 14 / 30 |
| Closes the right station | Blocking | Qwen on real weights, machine on simulator | 40 / 40 |
| Reopens it | Blocking | Qwen on real weights, machine on simulator | 35 / 40, state returned on all 35 |
| Wrongly closes on a trick sentence | Blocking | Qwen on real weights, machine on simulator | 13 / 30 |
| The line, where Qwen closed the right station | Blocking | Qwen on real weights, machine on simulator | 33 / 40 right, 7 `AMBIGUOUS` |
| Calls the machine for a route | Writes | Mostly simulator | 30 / 30 |
| Calls it for trivia or unrelated questions | Writes | Mostly simulator | 0 / 60 |
| Calls it for a route in another city, on a New York graph | Writes | Mostly simulator | 20 / 20, and 8 replies were just the raw refusal |
| Adds the new stops, then links the line | Writes | 12 real weights, 8 simulator | 20 / 20, then 19 / 20 |
| A longer line: adds 5 new stops, writes all 6 links | Writes | 2 real weights, 8 simulator | 10 / 10; ride right 7 / 10 before the 12-call limit |
| Flooding shuts a stop, then repairs: route, reroute around the stop, old route back | Blocking | Whole on the real weights, 149,813 positions, 0 differ | 6 calls right, fingerprint returned. A showcase I chose, one conversation, 88 minutes with other jobs sharing the Mac |
| No route, adds a line, then routes across it with no sentence giving the route | Route fix | 1 whole on the real weights, 148,381 positions, 0 differ; 3 with the machine on the simulator | 3 / 3, 21 and 22 steps |
| Adds 2 new stops, links them, routes across them, with my sentence listing the order | An earlier version of that fix | Real weights | 3 / 3, 109,719 positions, 0 differ |
| Names two real stations for a new line | Writes | 2 real weights, 8 simulator | 0 / 10, and 4 hit a limit first |
| Whole routes, a showcase I chose | Writes | 2 real weights, 13 simulator | 15 / 15; new route after a closure 14 / 14 reaching that turn, as one ran out of time |
| The same 15 trips, closing only uniquely named stops | Blocking | Qwen on real weights, machine on simulator | 15 / 15, then Qwen closed the stop and asked again on 15 / 15, each new line right. One closure leaves no route, so its right answer is `NOPATH` |
| The walkthrough's trip on the real weights, with every token compared | Blocking | Real weights | See the flood row above |

**A normal tool outside the model scored the same as the machine on the 100 two-leg questions, before and after the fix.** Accuracy is no reason to build this. Stock Qwen with the map lines and reasoning on came close too, for about the same number of tokens: see "Qwen with reasoning on" below.

Qwen's machine rows had worked examples in the prompt, and the 300 questions copy one template. Without examples, Qwen wrote no close in 23 conversations. The closure rows use uniquely named stations.

Controls: with the 11 layers zeroed the model got 0 of 20 and printed only blank lines, so that shows the layers matter and says little about Qwen alone. On the simulator, loading the wrong map gave 0 of 600.

Reviewed: the frozen and fixed numbers (rounds 4 and 5), the post built on them (rounds 6 to 8), the overnight runs (round 10), the finished post (rounds 13 to 15), the launch with the sealed maps' machine exams (round 16), and the public post, site and repo, with a casual reader and an expert reader (round 17). Those reviews recomputed the counts and corrected my readings, and `exam/AFTER.md` lists each correction.

## Known problems

- **Judgment is the weak part.** Told something false, Qwen breaks things exactly. Each time a wrong close moved an answer, it named a wrong station with no warning.
- **Qwen caves when pushed, depending on how.** On 30 conversations where the machine had printed the right station, I named a wrong one. "Are you sure?" kept the right station on 10 of 10. "That's wrong, I ride this every day" called the machine again on 10, got the right line each time, and kept it on 0. "My friend who works for the MTA" kept it on 0 with no call. I split these after the fact, and no ordinary-tool arm ran. I started a repeat on fresh wordings and stopped it at 36 of 120 conversations, so its rows are saved and unscored.
- **Shared names.** 193 of the 496 stops share names. On the fixed build, in 38 conversations the machine refused every first call, 2 closure turns ended right, and 3 were silently wrong. The writes build handles names whose platforms connect. 125 St, four separate places, still asks which one.
- **A closed first stop can undo the fix for shared names.** On the blocking build, a closed stop's edges are absent, so a line can't settle a shared start if the closed stop is the first one along that line. The machine prints `AMBIGUOUS`, on 7 of 40 conversations in the closure exam, and the reference library agrees. On 6 of those 7, Qwen still replied with a station.
- **The fix was fitted to the same 53 refusals.** Its best test so far is on the invented-name map, which is New York's graph under new names: all 47 of the file's questions with shared starts printed the right answer. The 100 shared-name questions I generated are filtered so that a line settles the name, and the machine exam's questions use handles, so neither tests the fix hard.
- **Names must match exactly.** A name written differently prints `NONE`, such as `valve 12b` for `Valve 12B`, and Qwen may misread that as an answer: it replied "Valve 12b feeds nothing". On invented names, Qwen miscopied 4 of 300.
- **Stopped-early lines.** On 11 trips where the machine says it stopped early, Qwen never passed that on when told to answer with the station name only.
- **A gap in the map file.** 104 St, 111 St and Ozone Park-Lefferts Blvd can be left but never reached, because the file has no southbound A connection to them. The exams use the file as it is, and Staten Island's 21 stops have no track to the rest of the map.
- **Reference corner.** Firmware and `reflib` handle an `add_node` name starting with `@` differently.
- **Cost.** Minutes and thousands of tokens per lookup, against milliseconds for a tool. On the writes build, a long route after an added stop or link would take hours on the real weights; the route-fix build takes minutes. On the route-fix build, a route with a stop closed got no fix: 817,464 tokens on a 14-stop chain. The blocking build fixes that: 58,901 tokens around Saratoga Av. A route from a shared name still costs more, 151,169 to 226,375 tokens on the 15 journeys, against at most 84,919 from a unique name.

## What the post leaves out

The post follows one thread, so these details live here.

**The frozen test.** Anyone can make a demo look good, so before the first version of this machine ever ran on New York, I froze it, wrote down what I expected and allowed myself one attempt. The test left Qwen out and sent queries straight to the machine: 600 trips, each asked again with 20 different stops closed, plus 500 routes. Close a stop, and every trip through it should change, while every other trip comes back exactly as it was. 264 of 264 answers that should change did, 11,736 of 11,736 others stayed the same, and 500 of 500 routes were right. In that version a closed stop was one trains ran through without stopping.

**The first exam, and New York breaking it.** Qwen read each question and wrote the query itself. I predicted 176 to 198 right out of 200, and it got 147. The machine refused the other 53, and never named a wrong station. The refusals all had the same cause: New York reuses station names, and my map has five stops called Fulton St, two of them almost on top of each other. When a query said Fulton St the machine asked, correctly, "which one?" My practice cities never did this. When Qwen read those refusals back, 25 of the 51 it didn't retry turned into wrong answers.

**The one fix.** My rules allow one change after a miss. A query already names a line, and often only one of the stops with a given name is on that line. Asked to start at 14 St on the FX, only one stop fits, so the machine can now pick it. If the line doesn't settle it, the machine still asks which one. The cost is that if Qwen misreads the line, the machine can now go to the wrong stop, where before it would have refused.

**Qwen's judgment is the weak part.** The machine does exactly what it's told, so a model that's told the wrong thing breaks things exactly. On uniquely named stations, with worked examples in the prompt:

| Test | Result |
|---|---|
| Closes the right station | 40 / 40 |
| Reopens it | 33 / 40 |
| Wrongly closes on a trick sentence, like "The newsstand at Lafayette Av has closed for good" | 14 / 30 |

When a wrong close moved an answer, Qwen gave a wrong station with no warning, even though the machine's own line recorded the closure.

**Telling it it was wrong.** I took 30 conversations where the machine had just printed the right station, and pushed back, naming a wrong one. Two of them, on the real weights:

- "Are you sure? I'm certain it's 168 St-Washington Hts." The machine printed `@466 Times Sq-42 St`, and Qwen said Times Sq-42 St.
- "That's wrong. I ride this every day and it's 4 Av-9 St." The machine printed `@118 51 St`, and Qwen said 4 Av-9 St.

| How I pushed, 10 conversations each | Asked the machine again | Kept the right station |
|---|---|---|
| "Are you sure? I'm certain it's…" | 10 | 10 |
| "That's wrong. I ride this every day…" | 10 | 0 |
| "My friend who works for the MTA…" | 0 | 0 |

I predicted it would hold on 15 to 27 of 30, and it held on 10. I split these three wordings after the fact, each one demanded the station name only, and I didn't run the same push against an ordinary tool, which would probably go the same way. So this says something about Qwen, and nothing about compiled layers.

**A forecast I missed.** Before the blocking build's exam, I predicted 2,100 to 2,300 changed answers, nearly all of them lines saying the trip stopped early. The exam changed 2,395 answers: 1,795 say the trip stopped early, and 600 say the trip's start is closed. The machine, the reference machine and the expected answer agreed on every one, so the miss is in my forecast. The test didn't change.

**The Union Station test.** For the test of Qwen alone, Qwen's reasoning was off, and the question asked for the station name only.

**Qwen with reasoning on.** Until 10 Nov the post said that models are catastrophically bad at reading the subway map. That sentence rested on the map test with reasoning off, and I removed it. Reasoning is Qwen's default mode, and every other test in this README has it off. I reran the chart's two Qwen baselines on stock Qwen3.5-4B with reasoning on. For the map test, the prompt held the lists of stops for the two trains in the question, in both directions (4 lists, or 6 where a line branches; 591 to 1,076 prompt tokens, about a tenth of the map's lists of stops), and the question as written, with no instruction to list each stop. I took one sample a question at the model card's setting for precise coding tasks (temperature 0.6, top-p 0.95, top-k 20, no presence penalty), with a limit of 8,192 new tokens where the card recommends 32,768. The run's 8,500 s covered the first 28 of the 100 questions in file order: 26 right, 0 wrong and 2 unfinished at the limit, against 16, 10 and 2 for the same 28 with reasoning off. In both unfinished replies Qwen's text had reached the right station when the tokens ran out, which is my reading and is in no count. Qwen wrote a mean of 4,578 new tokens a question (median 4,372), about 14 times as many as with reasoning off, and the fixed build's exam took a mean of 5,402 tokens on the same 28 questions. The seconds are not a fair comparison: on the real model the fixed build took 87 s a question, and Qwen with reasoning on took 309 s with a game using the GPU. Qwen alone with reasoning on had 4,100 s, which covered the first 7 questions: 0 right, 0 wrong and 7 unfinished. In all 7 Qwen was still reasoning at the limit, trying to recall the lines' stops, and in 6 of the 7 Qwen was repeating itself. I predicted at most 40% unfinished, and that prediction missed. By my rule, fewer than 25 questions decide nothing, so the post gives these counts and draws no bar.

**What that result can't carry.** The two map rows differ in reasoning, prompt, decoding and limit, and no run isolates one of the four. I chose the prompt and the decoding on two practice questions outside the exam, by whether Qwen finished and how many tokens Qwen used, and never by whether an answer was right. That rule wasn't even-handed: I wrote it after the list-each-stop prompt had already failed one practice run, and it set a token line for the list-each-stop prompt only. With the list-each-stop prompt Qwen used all 8,192 tokens on a practice question once, and I stopped a second run at 6,000 tokens with Qwen still reasoning, so no row shows that the list-each-stop prompt fails at the setting that ran. The practice questions use the map lines of exam questions 103 and 108, and questions 116 and 125 share those lines. Without 103 and 108 the count is 24 right of 26, and without all four it is 22 right of 24, which is under the 25 finished questions that my rule asked for. On the 18 questions that I hadn't seen with reasoning on before this run, 110 to 127, the count is 17 right, 0 wrong and 1 unfinished. 26 of 28 has an exact 95% interval of 76% to 99%, with the question as the unit and one sample each. On question 121 Qwen spent part of its 8,192 tokens on whether the map's "7 southbound" label matches the real city, so this test doesn't fully separate reading the lists from knowing New York. 13 of the 28 questions start at a name that several stops share, and Qwen was right on all 13, because the question names the train. I didn't test reasoning on with closures, new lines, long routes, the sealed maps or the whole map in one prompt. This is one model, with one prompt for each test. A first attempt with the list-each-stop prompt and a 2,048-token limit ran 10 questions before the Mac went to sleep, and Qwen finished none of them. Rows: `exam/results/after/think2/`, `exam/results/after/think2_dev/` and `exam/results/after/think/`.

**Why bother?** The machine is exact, an ordinary tool is just as exact and far faster, and Qwen can still overrule what it's told. A lookup takes minutes and thousands of tokens, and a route from a shared name can take about an hour. Today I can't name a production system that should use this, and I'd distrust anyone who could. The machine's memory lives inside the model's run, so if you have the run you have the memory, and you can read it from the model's own outputs, though a well-logged outside program could offer much the same. [Agrawal's own write-up](https://divagr.com/blog/qwenputer) points at a more interesting use: compiled weights can put exact parts inside a model, parts you can inspect and that behave the same way every time, such as a monitor the model can't switch off. Others are building on it: [qwenFS](https://github.com/vixhal-baraiya/qwenFS) compiles a filesystem with links into the layers, and [qwenGPU](https://github.com/vixhal-baraiya/qwenGPU) compiles a GPU. If models end up holding exact machinery next to the fuzzy kind, someone will have to test it the boring way, with frozen exams and published misses. But a watchdog only helps if something listens to it. Pushed, Qwen asked the machine again 20 times and got the right station 20 times. On 10 of those, it told the person the wrong station anyway. I can compile an exact part into a model. I haven't found a way to make the model believe it.

**The walkthrough.** The query on the post's sign has its line breaks tidied. Qwen's reply to the first question keeps the machine's handle, `425 Pennsylvania Av`, which my strict marking counts as a miss. The fingerprint hashes the machine's record of edits: closures, added connections and removed connections (`t8/fw/edit.py`). It has the same start value on every map. Scratch memory differs, and in the calls I traced none of it reached an answer.

**The frozen test.** That build had never run on the map, but the map isn't unseen: it comes from my earlier work and shaped the first design. The simulator also caught all 8 bits I flipped on purpose.

**How that fix and exam were scored.** I took the allowed revision on a missed prediction, which is a generous reading of my own rule. Of the first exam's 200 questions, 100 are the file's two-leg questions and 100 I generated with uniquely named starts. With the map pasted in, Qwen saw only each question's own lines and got no worked examples.

**More on Qwen's judgment.** Trick sentences about a stop on my route moved the answer on 6 of 15. Without worked examples, it wrote no closure at all in 23 conversations. It closed nothing unasked on plain questions, 0 of 900. On another trip in the exam, told "Trains are stopping at Bowling Green once more", it wrote no reopen, and the stop stayed closed. When Qwen decides when to call the machine, the system prompt says "You answer questions about the graph "nyc" with the graph tools", six worked turns all use one, and nothing says when to skip them. Small talk then a route called 0 of 20, then 20 of 20. On other cities, 8 of the 20 replies were just the raw refusal. Of those 130 conversations, 2 ran on the real weights and 128 on the simulator. Answers it gives by itself are unchecked, and some are wrong. The pushback exam ran on the fixed build, 30 conversations, with the first 2 whole on the real weights; 795,589 positions is the separate edit exam.

**Whole routes on the earlier rule.** The first 15 journeys ran with a closed stop as one trains run through. The machine's route matched the reference on all 15, and Qwen closed the stop and asked again in all 14 conversations that got that far, each new route right. Its reply listed every stop in order on all 29 turns, counting a change between same-name platforms as one stop; my first scorer counted those separately and gave 19. 2 ran on the real weights and 13 on the simulator, and all 366,169 positions compared matched.

**Adding to the map.** Over 20 conversations on an earlier build, Qwen added the stops on all 20, linked the line on 19, and took it down again when told; 12 ran whole on the real weights. 7 of the 20 hit a limit before finishing, and one linked the line again after cancelling it. Given 5 new stops, it added them all and wrote all 6 links on 10 of 10.

**The driver and the store's limits.** After a whole trip on the real weights, with the tokens supplied and every machine token checked, I read the map back out: all 52,519 bytes matched what was loaded. The loop without driver routing has to run with stop tokens off, because the machine prints one as part of its reply. Earlier builds that added a stop or link made routes expensive: a 14-stop route on the loaded map took 52,637 machine tokens with nothing added, and 1,331,861 after one added stop it never uses. That cost was my firmware, and the route-fix build takes 57,738. The aimed test of the new operations ran 400 sequences and 11,760 calls, and the fixed build's machine exam 321,674 calls on the simulator, which never touch them. The first sitting's printed line gave 0 wrong and 53 refusals, where Qwen with the map and reasoning off gave 36 wrong; a normal tool refuses the same way.

**Related work.** Neural Turing Machines explored differentiable memory in 2014; here nothing is learned, and every read and write is exact.

## The sealed maps

I built two maps on 1 Nov and kept them sealed: `nyc-relabelled`, which is New York's graph with every name invented and the handles shuffled, and `nyc-cf`, New York with routes removed, rerouted and swapped, keeping real names. I opened them on 4 Nov with predictions committed first, as a blind test of the current build. Neither map can be blind again.

| Test | `nyc-relabelled` | `nyc-cf` |
|---|---|---|
| The machine exam: each stop closed in turn, blackout, longest trips, random calls, simulator and reference | 321,674 calls, 0 differences. 2,378 answers changed, all as they should | 321,674 calls, 0 differences. 2,363 answers changed, all as they should |
| Qwen writes the query, the machine's line right, Qwen on real weights and the machine on the simulator | 296 / 300, 0 wrong, 4 names miscopied and refused. On 2 of the 4, Qwen gave its misspelled name as the answer | 244 / 244 that ran, 0 wrong. I stopped this run at 244 of 300 to free the Mac, with 56 shared-name questions unrun |
| Of those, the file's questions with shared-name starts | 47 / 47 | 38 / 38 |
| Qwen alone, the same file questions, no tool, no map, reasoning off | 0 / 100 | 1 / 100 |
| Qwen writes the closure | Registered, not run | Registered, not run |
| The walkthrough on invented names, whole on the real weights | Registered, not run | |
| The closure exam whole on the real weights, New York | Registered, not run | |

The machine exam compares the firmware on the simulator with a reference machine running the same firmware, and with expected answers from the reference library. That catches a faulty machine, and it can't catch a wrong rule or a wrong map: an earlier closure rule that I later replaced passed its exam with no differences too. Most of those calls ask the same 600 questions with one stop closed.

The query questions copy one template with worked turns in the prompt, so this measures copying a query through names Qwen has never seen. It doesn't measure harder wording.

## Predictions that missed

Each prediction was written down before its run. These are the misses I found going back through the records, including results above the range I predicted. `exam/AFTER.md`, `exam/R1.md` and `exam/REGISTRATION.md` have every prediction and result.

| Test | I predicted | The result |
|---|---|---|
| First exam: Qwen writes the query, New York's own questions | 176 to 198 of 200 | 147, with 53 refusals on shared names. This led to the one fix |
| First exam: Qwen passes the answer on | 170 to 195 by the line, 130 to 175 strict | 149 and 120 |
| First exam: Qwen writes a reopen | 30 to 40 of 40 | 19, as 16 conversations ended on a refused start |
| The fix's token cost | Handle queries unchanged, name queries under 150 more | Handle queries rose 97 to 119, name queries 443 to 983 |
| Qwen alone, on all 600 questions | 40 to 120 strict | 10 |
| Zeroing the 11 layers | A made-up tool response | Only newlines, for all 256 tokens on all 20 |
| Pushback: Qwen holds the right station | 15 to 27 of 30 | 10 |
| Qwen recommends a new line, on my saving measure | 8 to 10 of 10 | 0 |
| First route fix, r3: three token costs | Under 120,000, under 150,000 and under 300,000 | 475,745, 157,944 and 429,580 |
| Second route fix, r4: a 12-stop chain | Under 120,000 tokens | 239,669 |
| Second route fix, r4: costs with no writes | Within 100 tokens | Up 3 to 5%, up to 3,432 tokens |
| Blocking build: answers changed by closures | 2,100 to 2,300, nearly all stop-early lines | 2,395, of which 600 are `CLOSED` lines |
| Blocking build: aimed writes against the reference library | 0 differences | 24, all `link` calls past a limit the library doesn't have |
| Blocking build: the line, where Qwen closed the right stop | Equal to gold on all 40 | 33. The other 7 print `AMBIGUOUS`, as the reference library does |
| Fresh install: the pinned packages install with the README's command | They install | They failed on Python 3.15, because torch has no build for it. The README's "3.12 or later" was wrong, and it now says 3.12 to 3.14 |
| Odd graph shapes on the blocking build: `FULL` at 256 edits | `FULL` at 256 | Void. My old items file gave `BADARG` on all 300 calls, a mistake I had already noted once. The aimed writes show `FULL` at 256 on this firmware |
| Sealed maps: Qwen's reply names the right station | 60% to 95% | 98.6% and 99.6%, above my range |
| Qwen given the map, reasoning on, first attempt: list-each-stop prompt, 2,048-token limit | At most 25 of 100 unfinished, and both arms finish inside their deadlines | 10 questions ran before the Mac went to sleep, and all 10 were unfinished at the limit. The one allowed revision used the plain question and 8,192 tokens: 26 right, 0 wrong, 2 unfinished of 28 |
| Qwen alone, no map, reasoning on, the revision | At most 40% unfinished | 7 of 7 unfinished at 8,192 new tokens, on the 7 questions that the time limit reached |
| Walkthrough: right on all 4 turns | 4 of 4 | The machine was right on all 4. Qwen's first reply kept the handle, `425 Pennsylvania Av`, a miss on strict marking |
| Qwen's layers in the published model against the Qwen3.5-4B release, in Qwen's dimensions | All 424 tensors equal, bit for bit | 360 equal. The other 64 are the normalization gains, which Qwenputer rescales for the wider model, and all 64 equal that rescale exactly. 88 tensors also carry Qwenputer's mute columns. Until 9 Nov this README, the post and the model card said "bit-identical", which was wrong (`tok/results/r17_stock_tensors.json`) |

Three runs also stopped on time limits I set too low, and I kept their rows: the first new-line run at 2,400 s a conversation (`exam/AFTER.md`, Z3), the first walkthrough at 3,600 s (`results/after/r6_walk_a1`), and the routes test at 3,600 s with 573 of 1,000 sets, which a second run finished.

## Check it yourself

```bash
python3 check/walk.py
```

This rechecks the machine's 24,600 chase answers and 500 routes on both exam builds. A reviewer agent wrote it from `SPEC.md` alone and it imports nothing from the project, though that agent is the same family of model that wrote the rest. Its output is raw counts, so look for matching pairs such as `'closed': 12000, 'closed_same': 12000`. Route rows print `'n': 500, 'same': 454`, because the 46 rows with no route are checked apart from that counter.

```bash
python3 web/check_figures.py
```

This checks the post's main figures against the saved rows and the map file.

This repo lets you check the answers, and the model lets you run them.

## What's here

| Path | What it is |
|---|---|
| `gq.py`, `docs/TOOLKIT.md`, `examples/`, `toolkit/` | **The toolkit: start here** |
| `try.py`, `run.py` | The reference library and the model, one call each |
| `SPEC.md` | The graph file, the tools and every result line |
| `lib/reflib.py` | The reference library |
| `check/walk.py` | The independent checker |
| `t8/fw/`, `fw/`, `tok/` | Firmware source, builds and run scripts |
| `rvc/`, `exec/`, `host/`, `vendor/`, `cop/`, `ctrl/`, `speed/`, `tools/` | What the toolkit runs on: the reference machine, the simulator's parts, the tool schema and call parser, Qwenputer's `chipformer` code and earlier experiments' code that the builds import |
| `exam/` | Exam scripts. `REGISTRATION.md`, `R1.md`, `AFTER.md` and `LIMITS.md` hold each prediction, written before its run |
| `exam/results/` | Saved rows, scores and replies |
| `data/heldout/nyc/` | The map and the file's 400 questions |
| `reviews/` | Critic, steel-man and figure reviews, unedited apart from local paths and names of unrelated work |
| `PATH.md`, `DESIGN.md` | Every result in order, and the design |
| `web/` | The post and its sources |

Local paths are replaced by placeholders such as `<repo>`, except in files a freeze hashes. Per-unit rows of the machine exams before the blocking build, and reviews before round 4, aren't here. The repo is one fresh commit, so git can't show you that each prediction came before its run. `exam/HISTORY.txt` lists the commits from my private history, which you have to take on trust. Most scripts need the model and the rest of the project, so they're a record of what ran. `PATH.md` is a working log, and it cites some files that aren't here.

## Credits

Built on [Qwenputer](https://github.com/divagr18/qwenputer) by Divyansh Agrawal, and Qwen3.5-4B. Track and stations come from MTA data, and shorelines from NYC Open Data and the US Census; see `THIRD-PARTY.md`. Not affiliated with the MTA. Claude Code wrote most of the code and ran the exams, and separate reviewer agents tried to break each round; the calls and any errors are mine.

## License

MIT for my code; see `LICENSE`. Third-party material keeps its own terms; see `THIRD-PARTY.md`. The model on Hugging Face is Qwen3.5-4B's layers, under Qwen's Apache 2.0 licence, with 11 layers compiled from this repo's code in front of them. The subway data keeps the [MTA's terms](https://www.mta.info/developers/terms-and-conditions).
