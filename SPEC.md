# X2.10 interface spec v0 (development; frozen with Phase A)

Every part of X2.10 shares this contract: the data builders, the reference library, the host-tool baseline, the C
library on the graph coprocessor, and later the circuit. Nothing in it is specific to one domain.

## 1. Graph file: `x210-graph/1` (JSON)
```json
{"format": "x210-graph/1", "name": "nyc", "domain": "transit", "noun": "station",
 "nodes": [{"label": "Van Cortlandt Park-242 St", "prop": 0, "src": "101"}],
 "relations": ["1 northbound", "1 southbound", "transfer"],
 "edges": [[0, 1, 1, 0]],
 "splice": ["1 northbound", "1 southbound"],
 "change": "transfer",
 "meta": {}}
```
- **Nodes.** A node's handle is its index in `nodes`, from 0 to N−1. Builders order nodes by (label, src), so handles
  are canonical.
  - `label` is the name. Several nodes may share it.
  - `prop` is an integer from 0 to 65,535, defaulting to 0.
  - `src` is the source id and is not used by the machine.
- **Relations.** `relations` lists the names. A relation is any string and has no built-in meaning.
- **Edges.** Each edge is `[from, rel_index, to, weight]`, with the weight from 0 to 65,535. Edges are directed.
  - A symmetric relation is listed in both directions.
  - Duplicate (from, rel, to) triples are not allowed. Self-loops are allowed.
  - Edges are sorted by (from, rel, to).
- **`splice`** names the relations that `close` routes through: predecessor to successor. `close` deletes edges of
  every other relation.
- **`change`** is the relation that `chase` uses to change between legs; it may be null.
- **`noun`** is the graph's own word for a node, used only by the cleaner (§4): `station` for `transit`, null for every
  other domain, so a null noun cleans punctuation alone. Builders set it from `domain` (`noun_for`, `data/build/common.py`).
  A file without the field has no cleaner: exact matching only.
- Builders write `<name>.graph.json` and record its SHA-256.

## 2. Question file: `x210-questions/1` (JSON)
```json
{"format": "x210-questions/1", "graph": "nyc", "graph_sha256": "…",
 "questions": [{"id": 0, "kind": "chase", "text": "…natural-language question…",
                "call": {"fn": "chase", "args": {"start": "@412", "legs": "A northbound 3; 1 southbound 2"}},
                "answer": [87], "answer_text": "@87 72 St"}]}
```
- `kind` is the library function that answers the question. `call` is the canonical call; `answer` holds the handles.
- `text` is what Qwen sees. Templates come from the builder for the domain, and every phrasing set is recorded.

## 3. The tool interface (what Qwen calls; identical for the host baseline and the circuit)
Arguments are strings. A node argument is a handle (`@217`) or a label. A label is resolved first (§4), and an
ambiguous or unknown label returns that result instead of running the call.

| Function | Arguments | Result line(s) |
|---|---|---|
| `find` | `name`, optional `has` (a relation) | `@h label`; or `AMBIGUOUS k: @h1 label \| @h2 label …` (ascending handles); or `NONE name` |
| `follow` | `node`, `relation`, `steps` (1–255) | `@h label`; or a limit line, below |
| `chase` | `start`, `legs` (`rel n; rel n; …`, 1–16 legs) | `@h label`; or the first failing leg's limit line, below |
| `neighbours` | `node`, `relation`, optional `direction` (`out` by default, or `in`) | one `@h label` per line, ascending handles; or `NONE` |
| `path` | `from`, `to` | `k steps: @h0 label > @h1 label > … > @hk label` (fewest edges over all relations; canonical: §5); or `NOPATH` |
| `cheapest` | `from`, `to` | `cost c: @h0 label > … > @hk label` (Dijkstra, tie-break as in §5); or `NOPATH`; `OVERFLOW` above 65,535 |
| `close` | `node` | `closed @h label` (or `already closed …`) |
| `reopen` | `node` | `reopened @h label` (or `not closed …`) |
| `link` | `from`, `relation`, `to`, optional `weight` (0 by default) | `linked @a label > relation > @b label` (or `already linked …`) |
| `unlink` | `from`, `relation`, `to` | `unlinked @a label > relation > @b label` (or `not linked …`) |

- **`chase` with writes (graphs with the `noun` field; the `writes` firmware).** Two optional arguments, `closed` and `reopened`, each names separated by `;`, each name resolved as §4. After the legs are checked, `chase` applies every `closed` name, then every `reopened` name, as `close` and `reopen` would, then walks. Durable state is left as those functions leave it. The response states each write on its own line (with any reading line above it), then the result: `closed @88 Magnolia Junction-Harvest Park`, then `@12 72 St`. A write that gets `NONE` or `AMBIGUOUS` ends the call there, with earlier writes standing and stated, and no walk. `already closed` and `not closed` don't end it. The result is the last line.
- **Limit lines (Theo, 2 Nov).** A walk that can't finish says so in words. `chase` names the leg, and `follow` has one leg, so it leaves that out:
  - No edge: `Stopped early on leg i: after s steps at @h label, no further step along this relation exists. The journey did not finish.`
  - Several edges: `Stopped early on leg i: after s steps at @h label, there are k possible next steps, so the way on isn't unique. The journey did not finish.`
  - No change possible: `Stopped early on leg i: at @h label, no change leads to that leg's relation. The journey did not finish.`
  - `follow`: the same first two, starting `Stopped early: after s steps at`.
  - A file without the `noun` field (§1) keeps the old `END`, `MULTI`, `NOCHANGE` lines; `reword` in `lib/reflib.py` turns a saved old line into the new form.
- **`follow`.** It takes the `relation` out-edge `steps` times. At a node with more than one such edge, or none, it stops
  with a limit line.
- **`chase`.** It runs each leg as a `follow`. Before every leg after the first: if the current node has an out-edge
  in the leg's relation, it stays. Otherwise it takes one `change` edge to a node that has one, which must be
  unique. If none exists, or several exist, it stops with a limit line (several reads `after 0 steps`).
- **`path`.** Breadth-first search over the union of all relations, `change` included; every edge is one step.
- **Closed nodes.** `close` hides a node from `find` and from every search until `reopen`, with nothing rewritten.
  - Along a `splice` relation a closed node is transparent: a walk passes through it, and weights add.
  - Along every other relation, its edges are absent.
  - Closes and reopens commute and are exactly reversible.
  - A handle to a closed node answers `CLOSED @h label`.
- **Errors.** `NORELATION name`, `BADARG <param> <value>` and `NOFUNCTION fn`.
- **Limits** (shared by the circuit): `FULL`, `DEGREE`, `OVERFLOW`, `COLLIDE`, `PROBE`. The reference raises each one
  at the envelope bound recorded in Phase A.

## 4. Names
- A label matches when its whole text equals the argument after Unicode NFC normalisation and trimming of leading and
  trailing spaces. Matching is case-sensitive.
- A node argument may also be `@h label`, exactly as a response line prints it (measured: Qwen copies that form). The
  label must match node h, or the answer is `NONE`.
- With `has`, only nodes that have an out-edge in that relation match.
- Phase A measures which spellings Qwen actually writes. Any normalisation added afterwards is listed here before the
  freeze.
- **The strict cleaner (Theo, 2 Nov).** It applies only when a name, not a handle, has matched nothing, and it applies to every
  node argument.
  1. Remove trailing punctuation (`.,;:!?`) and whitespace from the name. If that changed it, and it now matches, use it.
  2. Otherwise, if the name's last word is the graph's noun for a node (§1), with whitespace before it, remove the word and
     then trailing punctuation and whitespace again. If it now matches, use it.
  3. The first form that matches anything decides. It must name exactly one node. If it names several, or nothing matches,
     the answer stays `NONE` with the name as written.

  Case matters and no other word is removed, so `192 St station.` reads as `192 St`, while `192 St Station` and
  `Out of 192 St` stay `NONE`. Exact matching always comes first, so a label that really ends in the noun is found as itself.
- **A reading is stated.** Each name read this way adds a line before the result: `name read as @h label`. So the
  response to `start: 192 St station` is two lines:
  ```
  name read as @60 192 St
  @78 E 76 St
  ```
  The result is what the response would have been for the name as read; `split_reading` in `lib/reflib.py` separates the two.
  Print mode's answer is the result, and a scorer judges the result. Direct calls to reflib's methods return the result
  alone; `Graph.call` is the tool and returns the whole response.

## 5. Canonical choices
- Ties always go to the lowest handle.
- For `cheapest`, nodes are finalised in (cost, handle) order. Each node's predecessor is the lowest-handle
  node, among those finalised before it, that reaches it at its final cost.
- For `path`, each node keeps the lowest-handle predecessor among nodes in the previous BFS level. The path is rebuilt
  from `to` backwards.

## 6. Response wrapping
The circuit prints `<tool_response>\n` + result lines joined by `\n` + `\n</tool_response>`, which is Qwen 3.5's
template. The host baseline prints the same bytes.

## Freeze note (2 Nov, `exam/REGISTRATION.md`)
The exams apply `noun.with_noun` and `reflib.reword` when loading a graph and its golds; the files are unchanged. The machine prints `TOOLONG` past its 80-token capture window. Known differences between machine and reflib, none in a real call: `t8/fw/results/writes_fuzzfw.json`, 80 of 28,490 fuzz cases by class. A stale capture, lone UTF-8 bytes and NUL are known limits. Response wrapping also carries the machine's `<think>` lines, as in `rvc/box.py`'s tail.
