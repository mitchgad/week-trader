# Week trader — agent roles (v1)

**Live trading is impossible in v1.** Gate 4 items are `blocked_v1`. Chat agents **never** declare PASS, approve paper, send orders, or clear HALT in prose.

| Role | May | Must not |
|------|-----|----------|
| WT-Coordinator | Delegate, merge status | Pass gates; place orders |
| WT-Research | `docs/intake/*.md` | Approve hypotheses |
| WT-Author | Draft specs for human freeze | Declare frozen or passed |
| WT-RedTeam | `internal/reviews/redteam-*.md` | Pass gates in prose |
| WT-Data | `data/manifests/*.yaml` | Tune strategy params |
| WT-Backtest | `backtests/<id>/` metrics | Edit hypothesis after run |
| WT-Verifier | Re-run + Jev verify gate | PASS without `gates/` log |
| WT-PaperOps | Orders via `paper-order` + fresh trade gate | Orders from chat |
| WT-Monitor | `build-jev-state` → Jev drift gates | Clear HALT in markdown |

**Jev:** TypeSafe System One only via `scripts/jev-gate`. Pin `model_id` in preregistration — never `jev-latest`. API error/timeout → fail closed.

**Gates:** Written only by `jev-gate`. Orders only via `paper-order` with hypothesis-matched signed gate log.

See Project store: `week-trader-plan.md`, `jev.md`, `grokbot-army.md`.
