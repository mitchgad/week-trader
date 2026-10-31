# HALT dry-run (Phase 1)

Before first paper order on any hypothesis:

1. Create `paper/<id>/HALT` (empty file or `reason: dry-run`).
2. Run `paper-order` with a valid trade gate log — **must exit non-zero** and perform **zero** broker HTTP calls.
3. Remove HALT only after **Jev HALT-clear gate** + code checks (not chat).

Emergency human halt: create `HALT` anytime; Paper Ops and `paper-order` block while present.

Clear path requires `scripts/jev-gate` with `GATE=halt_clear` and signed log — agents must not declare clear in prose.
