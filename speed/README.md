# speed/fast.py: the standard runner for X2.10 question runs

Runs questions through Qwen and the machine, up to 15 at once on the GPU, with the same tokens as the slow path where a proof says so. **A firmware and flow with no proof run slow and say so in every record.** `proofs.json` is the list; `PROOFS` below says what each entry rests on.

## Use

```
PY=<qwenputer>/experimental/riscv/.venv/bin/python
cd xseries/X2.10/speed
PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 PYTHONDONTWRITEBYTECODE=1 \
  python3 ../tools/memguard.py --limit-gib 32 --log mem.log -- $PY fast.py \
    --machine tok --flow read-t6 --questions Q.json --out ../myfolder/results/run1
```

`Q.json` is `[[graph, question id], ...]` or `{"draw": [...]}`. The same from Python, one machine per process:

```python
sys.path.insert(0, ".../speed")
import fast
fast.setup("tok")                        # or setup("tok", elf=PATH, ckpt=PATH)
meta = fast.run(fast.items(pairs), fast.flow("print-chain3", limit_stop=True), "results/run1")
```

| Parameter | Meaning |
|---|---|
| `--machine` | `tok` (normal tokens, `tok/build/tok.elf`, `~/Models/x210/x210-tok`), `fw` (byte tokens, `fw/build/fw.elf`, `~/Models/x210/x210-rvc`), `clean` (t8's strict cleaner, once built). This picks the delivery |
| `--elf`, `--ckpt` | Other firmware or checkpoint. The proof lookup goes by the ELF's sha256. Blocks must come from that checkpoint; the runner checks |
| `--flow` | `print-chain3` (one tool, 2 retries), `print-chain4` (plus prefill and note), `print-one` (one call, no retries), `read-one` (one tool, Qwen replies, no sentences added; 12 calls, 768 a turn, 3,072 a question), `read-t6` (ten tools, Qwen answers in its own words) |
| `--speed-flags` | Print only. `--limit-stop`, `--cap 320`, `--lazy-echo` together |
| `--readback N` | Print only: after the answer, Qwen's own words up to N tokens, unscored |
| `--rows` | Rows per GPU step, 1-15. Default 8 |
| `--stock N` | Whole questions rerun in stock lockstep after the run. Default 2 |
| `--deadline-s` | Starts no new question after this |
| `--force fast\|slow` | Proof runs only. A forced run says so in every record |

**Output in `--out`:** `all.jsonl` (each question whole, tokens and text; a rerun skips finished ones), `meta.json` (firmware hash, checkpoint, flow, path, speed), `stock_sample.json`. Exit code 3 means a lock error, an engine flag or a stock disagreement: the run doesn't count until explained.

**Memory:** fast 12 GiB, slow and stock sample 20 GiB. Use memguard at 32 if the stock sample is on. One block file per checkpoint, at `~/Models/x210/*-blocks`; `fast.py --build-blocks MACHINE` makes one in under 5 minutes.

## Flow flags change what happens after the first line
They are off unless asked for, and read mode refuses them. Each has its own proof key.

| Flag | What it does | Cost |
|---|---|---|
| `--limit-stop` | A limit line (`END`, `MULTI`, `NOCHANGE`, `CLOSED`, `NOPATH`) ends the turn | A limit line on a wrong query gets no second try. On `chain4_fresh`, 18 of 100 reach one, all at the first line, all with that line as final, and it saves 36% of text steps. **A note-led retry ending on a limit line has never occurred in saved data, so what the stop does there is unmeasured:** it would end the turn without the second retry |
| `--cap N` | An attempt with no call ends at N tokens, not 768 | 96 loses all 4 rescues on chain3's records, 256 loses 1, 320 none. 320 is fitted on those records. Prose saved for reading is cut |
| `--lazy-echo` | Echoes reach Qwen's layers only if a retry follows | Print only. Qwen never sees the last line |

## What is different from the slow path
- **Execution, all flows:** Qwen's linear maps are nonzero blocks; a batched path; the residual's wide mean row by row; attention row by row; prefill from the engine's residual, no chip layers. Chip tokens on the C engine, as on every executor run.
- **Dropped:** the head-argmax check at owned positions. The stock sample checks it on whole questions, and it's 0 on every record so far.
- **Kept:** the reference lock on every burst.
- **Label each result "executor, fast path"**, as the fast path has no chip weights loaded.

## What it can't do yet
- Tools or flows other than the presets.
- A flow with no proof entry runs slow. That includes any new firmware until its sample passes.
- `exec/`'s other gate conditions aren't wired in: coverage differences, per-call reference digests.
- More than one machine in a process. Base Qwen with no machine: the host rows need this and it isn't built.
- Prefills don't batch. They're about a third of a print-flow question.
- The chip layers in C from the checkpoint's tensors (`wexec`) are not an option here yet.
- `--note` on normal tokens is a fixed sentence the runner feeds as tokens, not firmware output.

## PROOFS
Same tokens against the slow path on the stated sample, a stock sample in lockstep, on this hash and flow. Shared GPU, dev questions, not reviewed.

| Firmware | Flow key | Sample, fast against slow | Stock sample | s a question, fast / slow |
|---|---|---|---|---|
| `clean.elf` 278e96aa | `print-one` | 32 of 32: 16 dev cities, 8 limit lines, 8 hard; 7 read a name, 9 hit a limit line | 2 questions, 5,669 positions, 0 differ | 9.8 / 18.9 |
| `clean.elf` 278e96aa | `read-one` | 32 of 32, same questions | 2 questions, 8,664 positions, 0 differ | 12.6 / 27.3 |
| `tok.elf` 541e9ec9 | `print-chain3` | 32 of 32 | 2 questions, 9,627 positions, 0 differ | 17.6 / 30.6 |
| `tok.elf` 541e9ec9 | `print-chain3` + speed flags | 32 of 32 first calls, lines and finals only | P2's | 9.7 / 30.6 |

**Not proven, so they run slow:** `read-t6` on `tok.elf` (38 of 38 same as T6 before it was stopped, no stock sample), `print-chain4` on any firmware, anything on `fw.elf` through this runner (`fastrun.py` gave 98 of 98 on chain3's flow, a different script), any other hash.
