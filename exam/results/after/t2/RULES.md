# Scoring "Qwen wrote the right call"

A turn passes when Qwen's calls include every call of one listed alternative, and no unlisted write took effect. I score calls, not replies.

**Argument spelling.** An argument counts if it is the listed name, or the firmware resolves it to the listed node: a handle, `@h label`, or the cleaner's "name read as". A misspelling that prints `NONE` doesn't count, but a correct retry does. Relation names must match exactly. No `direction` equals `out`. A number the user states must match as `weight`; otherwise any weight passes.

**Extra read-only calls** never fail a turn, even on a no-call turn.

**Different order.** Calls within a turn may come in any order, except `add_node` before a `link` that needs it.

Each turn is scored alone, whatever earlier turns did to the state.
