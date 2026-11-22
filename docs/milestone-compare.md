# Milestone compare: before vs after

This document compares the accepted/submitted baseline with the current state of
Cite so the milestone change is visible and verifiable.

- **Baseline:** `514494b` — *Give the site a favicon* (pre-steward-fix state)
- **Current:** `0ec54a2` — *Point the project at the tested contract 0xB0295bcBe44271D194Da693BFd6844022F413958*
- **Scope of change:** `514494b..HEAD` — 17 files changed, 276 insertions(+), 24 deletions(-)

## Milestone fit

This work is meaningful new progress, not a resubmission of the same project:

| Milestone category | What changed | Evidence |
|---|---|---|
| Security / architecture improvement | Count-rule settlements can no longer bypass citation verification; claims cannot create payout obligations before the challenge window closes. | `contracts/cite.py` (`:1702`, `:2093`), regression tests in `tests/direct/` |
| Contract functionality / correctness | Event citations resolve to the correct original event-source URL instead of the measurement-source list. | `contracts/cite.py` (`:2319-2331`), regression test in `tests/direct/test_tier2_counting.py` |
| New deployment | Corrected source deployed to a fresh studionet contract used by the project. | `deployments.json`, `frontend/.env.local`, `frontend/.env.example`, `README.md`, scripts |
| App / integration improvement | The advertised challenge action is exposed in the frontend with the 0.1 GEN bond flow. | `frontend/src/lib/cite.ts`, `frontend/src/components/BetPanel.tsx`, `frontend/src/app/markets/[id]/page.tsx` |
| Test / verification improvement | Regression tests added for each corrected path; full direct suite and real studionet integration tests pass. | `tests/direct/*`, `tests/integration/test_cite.py`, `docs/steward-fixes.md` |

## Before / after comparison

| Area | Before (`514494b`) | After (`0ec54a2`) |
|---|---|---|
| **Count-rule + citation-required settlement** | The counting branch could force `resolved = True`, overriding earlier citation checks. | The counting branch only settles when `parsed["resolved"]` still passes citation checks. |
| **Claim timing** | `claim` could reserve a payout obligation while the market was still in the challenge window. | `claim` rejects with `the market is still in its challenge window` until `_now_ts() > challenge_deadline_ts`. |
| **Event citation URL** | Event citations were looked up in the measurement source list, producing wrong/empty URLs. | Event citations are offset by measurement count and resolved against `event_urls`. |
| **Challenge action in app** | Challenge was visible in trail display but there was no frontend write action. | `challenge()` write action added; BetPanel exposes challenge UI when the challenge window is open; bond is 0.1 GEN. |
| **Regression coverage** | No regression tests for these steward-reported paths. | Added regression tests for count-rule citation void, event citation URL, and claim-during-window refusal; updated affected payout tests to respect the window. |
| **Deployed contract** | `0xeA384Ef9a0d8F87314ddb40d58F0183e69E0707b` (studionet, 2026-10-21) | `0xB0295bcBe44271D194Da693BFd6844022F413958` (studionet, corrected source, validated) |
| **Frontend build** | Built against previous contract/config. | Rebuilt against the corrected/tested contract; `tsc --noEmit` and `next build` clean. |
| **Submission evidence** | Steward request unresolved. | Steward fixes documented in `docs/steward-fixes.md` with code locations, tests, deployment, and corrected revision. |

## Key code changes

### Contract (`contracts/cite.py`)

- **Citation guard for count-rule settlements:** do not force-resolve after counting; only compute and set the count when the settlement already cleared citation checks.
- **Claim window gate:** refuse claim before the challenge window closes so no payout obligation is created prematurely.
- **Event citation URL mapping:** resolve citation `source_index` to measurement or event URL based on measurement count.

### Frontend

- **`frontend/src/lib/cite.ts`:** added `challenge(walletAddress, provider, marketId, evidenceUrl)` write action calling `challenge_market` with `value = gen(0.1)`.
- **`frontend/src/components/BetPanel.tsx`:** added challenge input/button, challenge deadline awareness, and disabled state when evidence URL is empty.
- **`frontend/src/app/markets/[id]/page.tsx`:** passes `challengeDeadlineTs={market.challenge_deadline_ts}` to `BetPanel`.

### Tests

- **`tests/direct/test_tier2_counting.py`:** count-rule settlement without verified citation is voided; event citation keeps its event source URL.
- **`tests/direct/test_settlement.py`:** claim during open challenge window is refused; existing payout tests moved past challenge window.
- **`tests/direct/test_adversarial.py`:** payout-flow tests moved past challenge window where required by the new claim gate.

## Validation results

| Check | Result |
|---|---|
| `genvm-lint check contracts/cite.py` | Passed |
| `genvm-lint typecheck contracts/cite.py` | No type errors |
| `pytest tests/direct` | **107 passed** |
| `npx tsc --noEmit` (frontend) | Clean |
| `npx next build` (frontend) | Clean |
| `pytest tests/integration/test_cite.py` (real studionet) | **4 passed** after a transient RPC 502 retry |

## Commit trail

| Commit | Purpose |
|---|---|
| `4cad728` | Steward fixes: citation guard, payout timing, event citation URLs, challenge action |
| `bdf9dd4` | Point deployment records and docs at the corrected contract |
| `0ec54a2` | Point the project at the tested contract `0xB0295bcBe44271D194Da693BFd6844022F413958` |

## How to verify

```bash
# Contract checks
genvm-lint check contracts/cite.py
genvm-lint typecheck contracts/cite.py
pytest tests/direct -q

# Frontend checks
cd frontend
npm install
npx tsc --noEmit
npx next build

# Real-network integration (studionet, deploys corrected source)
pytest tests/integration/test_cite.py -v -s
```

## Notes

- The compare baseline is `514494b` because it is the last pre-steward-fix commit on `main`.
- The new contract address `0xB0295bcBe44271D194Da693BFd6844022F413958` is the corrected/tested studionet deployment referenced by the project.
- This milestone focuses on security, correctness, deployment, and verifiable test evidence; it does not claim external traction metrics.
