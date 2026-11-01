# Intake — C3 network adoption tilt (parked)

**Suggested id:** `c3-network-adoption-spot` (not built).

**Status:** Parked. No Jev, no orders.

## Family

Liu & Tsyvinski-style **crypto network activity** tilt ([RFS / NBER WP 24877](https://www.nber.org/papers/w24877); plan example [algorithms-and-paper-trade.md C3](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md)).

## Assignment constraint

**Crypto spot only**, not BTC or ETH. Alpaca paper already runs BTC and ETH spot sleeves owned by other hypotheses.

## Why parked

1. **Adoption / on-chain features** (active addresses, transaction growth) are not free, point-in-time vendor series in-repo; vendor lag breaks timing (plan C3 kill: delay >24h).  
2. A second Alpaca-traded alt with **network data bound in manifest** is not specified with a free PIT source ([research-gap-fill.md §5](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md)).  
3. Without both legs (signal series + tradable spot symbol), there is no falsifiable long-only spec.

## Resume when

Free or licensed PIT on-chain feed with documented availability timestamp + Alpaca spot symbol not owned by another hypothesis.
