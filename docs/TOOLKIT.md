# Building with the graph-qwenputer

The graph-qwenputer is a graph computer inside a language model. It holds any graph that fits its limits: stops and lines, people and managers, packages and dependencies, cities and flights. This page shows how to load your own graph and run it.

`gq.py` is the only command you need. Each step needs a little more than the step before.

| Command | What it does | What it needs |
|---|---|---|
| `import` | Makes a graph file from a CSV file | Python 3.9 |
| `check` | Checks the graph file against the firmware's limits | Python 3.9 |
| `try` | Runs calls with the reference library | Python 3.9 |
| `sim`, `check --firmware` | Runs the real firmware on the C simulator, on the CPU | Python 3.12 to 3.14, `requirements.txt`, Homebrew's LLVM, 3 small model files |
| `ask` | Asks Qwen, with Qwen's layers on the real weights and the 11 added layers on the simulator. `--whole` runs those layers on the real weights too | The above, the 18.8 GB model, a Mac with Apple silicon |
| `build` | Rebuilds the firmware | `sim`'s list, and Homebrew's lld (`brew install lld`) |

`sim`, `ask` and `build` need an ARM CPU, because the C engine uses ARM NEON instructions, and I've only run them on Apple silicon Macs. `CHIP_CC` picks a clang other than Homebrew's for the engine. `build` needs Homebrew's paths.

## 1. Make a graph

Write a CSV file with one edge on each row: `from,relation,to`, and a weight if you want one. A row with one name adds a node with no edges. Lines that start with `#` are ignored.

```
# examples/packages.csv
from,relation,to
app,depends_on,web
app,depends_on,auth
web,depends_on,router
```

```bash
python3 gq.py import examples/packages.csv -o packages.graph.json
```

`import` treats these rows specially:

- A first row that names its columns is a header, in any order and any case: `from` or `source`, `relation`, `to` or `target`, and `weight`. Without a header, the columns are `from,relation,to,weight`.
- A row that starts with `#` is a comment. `import` reports how many it skipped, so a name can't start with `#` in a CSV file.
- The same edge twice with one weight becomes one edge, and `import` tells you. With two different weights, `import` refuses the file.
- The same text always means the same node, so two people called John Smith become one node. To have two nodes with one name, write the graph file by hand.
- The weight defaults to 1 in `import`. The `link` call defaults to 0.
- `--both` and `--inverse` act when the graph is imported. A later `link` call adds one edge, in one direction.
- `path` crosses every relation, so with `--inverse` a route can run against the original direction. No call reads back one edge's weight, and `cheapest` prints only the total.
- `import` reads rows split by commas. A file split by `;` or tabs needs converting first, and `import` warns you if it finds no edges.

Edges have a direction. `import` has three options for relations:

| Option | Effect |
|---|---|
| `--both flight` | Each `flight` edge also runs in the opposite direction |
| `--inverse reports_to=manages` | Each `reports_to` edge also adds the reverse edge in the relation `manages` |
| `--splice line` | A closed node can be passed along `line`. Without this option, a closed node blocks |

You can also write the graph file by hand. The format is in `SPEC.md`, and `examples/team.graph.json` is a short example.

## 2. Check it

```bash
python3 gq.py check packages.graph.json
```

`check` reports each problem in plain words. These are the firmware's limits:

| Limit | Value | If you go over |
|---|---|---|
| Nodes | 1,024 | The graph doesn't load |
| Relations | 64 | The graph doesn't load |
| Bytes in a node's name when the graph loads | 64 | The graph doesn't load |
| Edge weight | 0 to 65,535 | The graph doesn't load |
| Edges | About 6,880 with 9-byte names, fewer with longer names | The graph doesn't load. `check --firmware` gives the exact answer |
| New nodes in one conversation | 16 | `add_node` prints `FULL` |
| New edges in one conversation | 256 | `link` prints `FULL` |
| Bytes in a new node's name | 31 | `add_node` refuses the name |
| Calls in one conversation of `ask` | 12 | The conversation stops, and later turns don't run. `ask` says so |
| Tokens in one call, with the call's wrapper | 80 | The firmware prints `TOOLONG` and changes nothing. `check --firmware` reports the `path` and `link` calls between your two longest names |
| Legs in one `chase` | 16, if the whole call fits in 80 tokens | 12 legs of `depends_on 1` already print `TOOLONG` |

A name must match exactly, including case, apart from trailing punctuation and spaces. The prompt lists relations and doesn't list nodes, so Qwen only knows a name from your question. A name it spells differently prints `NONE`. Names can repeat. A query by a shared name prints `AMBIGUOUS` unless a relation or a transfer settles which node you mean. A route from a shared name also costs more: up to about 226,000 machine tokens on New York, against about 85,000 from a unique name. Names must not start with `@`, and relation names must not contain `;`.

## 3. Query it

```bash
python3 gq.py try packages.graph.json path app libc
python3 gq.py try packages.graph.json neighbours regex depends_on in
printf 'close | crypto\npath | auth | libc\n' | python3 gq.py try packages.graph.json
```

Each line of input is one call, with arguments split by `|`, so a name read this way can't contain `|`. Edits last until the input ends. The calls are in the README's Operations table. `try` runs the reference library in Python, so it takes milliseconds and has no size limit. `try` also has no 80-token limit and no limit on new edges, so a call can work in `try` and print `TOOLONG` or `FULL` in `sim`. `try` also reads digits from any script as numbers, and the firmware reads only 0 to 9. `sim` marks that as `DIFFER`.

## 4. Run it on the real firmware

`sim` runs the firmware that the model runs. A C simulator does the work of the 11 added layers, so you need no GPU and no model weights. On every call, `sim` also compares the answer with the reference machine and the reference library. The exceptions are a `TOOLONG` call and a `link` that prints `FULL`, where `sim` tells you the limit, because the reference library has neither limit.

```bash
python3.14 -m venv .venv && source .venv/bin/activate   # 3.12 or 3.13 should also work. The pinned torch has no build for 3.15
pip install -r requirements.txt
hf download hopski/graph-qwenputer chipformer.json config.json tokenizer.json --local-dir model
python3 gq.py sim packages.graph.json --model model path app libc
```
```
4 steps: @0 app > @2 auth > @5 crypto > @9 bignum > @12 libc
  4,964 machine tokens, 1.4 s. Reference machine and reference library: agree.
```

The first run compiles the C engine, which needs Homebrew's LLVM (`brew install llvm`). A machine token is one step of the computer's work. On the real model, about 60 machine tokens take one second, so 5,000 tokens take over a minute.

## 5. Ask Qwen

```bash
hf download hopski/graph-qwenputer --local-dir model
python3 gq.py ask packages.graph.json --model model --examples examples/packages.examples.json --tools neighbours,path,close,add_node,link "What does web depend on?"
```

Each argument after the options is one turn of one conversation. Qwen's layers run on the real model, and the C simulator runs the 11 added layers, because the whole real model takes minutes for each lookup. Add `--whole` to run the 11 added layers on the real weights as well, with every token compared against the simulator. That takes about one second for every 60 machine tokens.

Qwen only writes a good query when the prompt shows it how. Three things control that.

**The graph's name and relations.** The system prompt names them, so choose relation names that read well: `depends_on` is better than `r1`.

**Worked examples, with `--examples`.** The file is a list of turns. Write examples that sound like your questions, and use names that aren't in your graph. Each result must have the exact form that the firmware prints. Run your calls with `gq.py try` to see the form. A turn that should make no call has `"calls": []`.

```json
[{"user": "What does parser depend on?",
  "calls": [{"fn": "neighbours", "args": {"node": "parser", "relation": "depends_on"}, "result": "@4 lexer\n@9 ast"}],
  "reply": "lexer and ast"}]
```

Without `--examples`, Qwen sees worked examples about trains. Those examples work on New York. They are a poor fit for other graphs.

**The tools on offer, with `--tools`.** Offer only the calls your questions need. A shorter prompt runs faster and gives Qwen fewer ways to go wrong. The calls are `find`, `follow`, `chase`, `neighbours`, `path`, `cheapest`, `close`, `reopen`, `add_node`, `link` and `unlink`.

I ran `ask` from a clean copy with an empty home folder, on 11 turns across `packages`, `flights`, `team` and New York. Qwen wrote the right call on all 11 by my reading, and all 16 firmware answers matched the reference library. I wrote those questions and examples. A reviewer agent then wrote three graphs of its own and 30 turns, 20 of them hard, before any run, and Qwen wrote the right calls on 24 of 30 by its rule, with all 42 firmware answers right. That rule scores calls and not replies, and 23 of the 24 ended in a reply. The rows are in `exam/results/after/t1/` and `exam/results/after/t2/`.

Check Qwen's output. The firmware is exact, but Qwen can write the wrong query, and Qwen can misreport a right answer. The README's "What the post leaves out" has the results.

## What is still about trains

The graph can be anything, but some wording comes from the subway work:

- The firmware's stop-early line ends with "The journey did not finish." Changing the line means changing the firmware and `lib/reflib.py`.
- `ask` writes the system prompt in `host/tools.py`. With a `change` relation, the prompt says "Changing between lines".
- Without `--examples`, Qwen sees worked examples about trains.
- `--domain transit` makes the firmware accept a name that ends in "station", such as "Ash Rd station". Other graphs don't need this option.

## What you can swap

| Part | Where it lives | How to swap it |
|---|---|---|
| The graph | A JSON file, loaded when a conversation starts | `--graph`, or the first argument of `gq.py` |
| The closure rule | The graph's `splice` list | `--splice`, or an empty list so that closed nodes block |
| Worked examples | A JSON file | `--examples` |
| Tools on offer | A list of names | `--tools` |
| The firmware | `fw/graphlib.c`, `t8/fw/gen.py` | Edit them, then `gq.py build` |
| The model | A Hugging Face folder | `--model` |

## Changing the firmware

The firmware is a C program for the RISC-V CPU in the 11 added layers. `fw/graphlib.c` is the base, `t8/fw/gen.py` applies each build's patches and writes `t8/fw/build_r6/graphlib_bytes.c`, and `tok/gen_fw.py` turns strings into token tables.

```bash
python3 gq.py build --model model
```

`build` prints the new firmware's path and the first digits of its hash. With no edits and clang 23.1.4, the hash is `3d66be3572228cec`, the firmware that the exams ran. Another clang can give another hash. `build` overwrites `t8/fw/build_r6/writes.elf`, so use `git checkout` to get the frozen firmware back. `sim` and `ask` use the new build at once, and the model file doesn't change, because the firmware is loaded into running memory. After any edit, run the firmware and the reference library against each other with `gq.py sim`.

To change what an existing call does, edit its function in the C source and the same function in `lib/reflib.py`. The two must agree, because `sim` compares them.

`t8/fw/gen.py` patches `fw/graphlib.c` by exact text and replaces `f_path`, `f_close`, `f_find`, `f_add_node` and `f_unlink`, while the helpers stay in the C base. So one result line can come from both files. `NOPATH`, for example, comes from the base for a route between unique names and from `gen.py` for a route from a shared name. Search both files for the text you're changing, and edit both. If a patch stops matching, `build` says so. If you miss a place, `sim` prints `DIFFER`.

A new call touches more places: `FN`, `NFN`, `PARAMS`, `REQUIRED` and the fast parser's `SLOT` table and key checks in the firmware, then `dispatch`, then `ARGS` in `try.py` and `toolkit/sim_run.py`, the schema in `host/tools.py`, and `lib/reflib.py`. I have rebuilt the firmware and changed its patches, but I haven't tested this path for a new call from scratch.

The CPU runs any RV32IM program that fits in 256 KB of code, 128 KB of read-only data and 32 KB of RAM. A program with no graph at all is outside what this repo tests. [Qwenputer](https://github.com/divagr18/qwenputer) is the place to start for that.

## Take only what you need

`import` and `check` need `gq.py` and `toolkit/calls.py`. `try` adds `try.py`, `lib/reflib.py` and `t8/fw/noun.py`. `sim` needs these 39 files, about 480 KB, with the three small model files beside them. A reviewer copied exactly these to an empty folder and got the same answers and token counts as the full repo. The first run writes `tok/build/` and `t8/fw/build/`. To pass them on, include `LICENSE` and `licenses/qwenputer-LICENSE`.

```
gq.py
toolkit/calls.py  toolkit/sim_run.py
lib/reflib.py  host/tools.py
cop/boot.py  cop/cop_ref.py
exam/mach.py  exec/covdiff.py
rvc/box.py  rvc/decode.py
t8/fw/build_r6/writes.elf  t8/fw/cov.py  t8/fw/noun.py  t8/fw/overlay.py  t8/fw/tokrun.py
tok/boot_tok.py  tok/cexec.py  tok/common.py  tok/compile_ir.py  tok/core.py  tok/engine.c  tok/fragments.py  tok/overlay.py
vendor/qwenputer-riscv/chipformer/__init__.py
vendor/qwenputer-riscv/chipformer/dsl/__init__.py  vendor/qwenputer-riscv/chipformer/dsl/graph.py
vendor/qwenputer-riscv/chipformer/q35/__init__.py  vendor/qwenputer-riscv/chipformer/q35/emit.py  vendor/qwenputer-riscv/chipformer/q35/ir.py  vendor/qwenputer-riscv/chipformer/q35/prims.py  vendor/qwenputer-riscv/chipformer/q35/tiny.py
vendor/qwenputer-riscv/chipformer/rv/__init__.py  vendor/qwenputer-riscv/chipformer/rv/asm.py  vendor/qwenputer-riscv/chipformer/rv/bridge.py  vendor/qwenputer-riscv/chipformer/rv/elf.py  vendor/qwenputer-riscv/chipformer/rv/hf.py  vendor/qwenputer-riscv/chipformer/rv/ref.py  vendor/qwenputer-riscv/chipformer/rv/spec.py
```

## Test your setup

```bash
python3 toolkit/test_toolkit.py
python3 toolkit/test_toolkit.py --model model
python3 toolkit/test_toolkit.py --model model --build
```

The first command needs only Python and tests `import`, `check`, `try` and the error messages. The second also runs the real firmware on the simulator, which takes about 5 minutes. The third also rebuilds the firmware, and needs Homebrew's lld. It expects the frozen hash only on clang 23.1.4, and it puts the frozen firmware back afterwards.
