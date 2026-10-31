# week-trader

Research → Jev-gated validation → paper trading. **v1: no live trading.**

Project specs live in the Week trader Project store (`docs/week-trader-plan.md`, `jev.md`, etc.). This repo is the executable scaffold only.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make lint-jev-questions ID=_template
make gate4-closed
```

Secrets (never commit): `TYPESAFE_API_KEY`, `GATE_LOG_HMAC_SECRET`, broker paper keys when Phase 3+.
