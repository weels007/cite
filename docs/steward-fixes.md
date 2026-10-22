# Steward response fixes

Source and tests that answer the GenLayer steward request:

> Please update the submitted source so citation-required and count-rule
> settlements cannot resolve without verified citations, claims cannot create
> payout obligations until the challenge window closes, and event or
> primary-source citations retain the correct original URL. Expose the
> advertised challenge action through the app and add regression tests for
> each corrected path, then link the corrected GitHub revision.

## 1. Citation-required and count-rule settlements

**Problem.** A count-rule settlement forced `resolved = True` after the model
had already been asked, which overrode the citation checks that run before it.

**Fix.** `contracts/cite.py:1702` — the counting branch now only settles when
`parsed["resolved"]` is still true, so a settlement that did not clear the
citation checks stays unresolved.

## 2. Claims and payout obligations

**Problem.** `claim` accepted a market that was still `resolved` inside the
challenge window and reserved the payout obligation immediately, even though
the status only flipped to `settled` after the window closed.

**Fix.** `contracts/cite.py:2093` — `claim` now refuses with
`the market is still in its challenge window` while
`_now_ts() <= challenge_deadline_ts`.

## 3. Event and primary-source citations

**Problem.** `get_citations` looked event citations up in the measurement
source list, so the returned URL was wrong or empty for event citations.

**Fix.** `contracts/cite.py:2319-2331` — event citations are offset by the
measurement count and resolved against `event_urls`.

## 4. Challenge action in the app

**Fix.** `frontend/src/lib/cite.ts:361` — added the `challenge` write action
(`challenge_market`, bond 0.1 GEN). `frontend/src/components/BetPanel.tsx` —
added the challenge UI and `challengeDeadlineTs` prop. `frontend/src/app/markets/[id]/page.tsx` —
passes `challenge_deadline_ts`.

## 5. Regression tests

- `tests/direct/test_tier2_counting.py` — a count-rule settlement without a
  verified citation is voided.
- `tests/direct/test_tier2_counting.py` — an event citation keeps its event
  source URL.
- `tests/direct/test_settlement.py` — a claim during the open challenge window
  is refused.
- Updated payout tests in `tests/direct/test_settlement.py` and
  `tests/direct/test_adversarial.py` to move past the challenge window before
  claiming.

## 6. Validation

- `genvm-lint check contracts/cite.py` — passed.
- `genvm-lint typecheck contracts/cite.py` — no type errors.
- `pytest tests/direct` — **107 passed**.
- `npx tsc --noEmit` (frontend) — clean.
- `npx next build` (frontend) — clean.

## 8. Real network validation

- `pytest tests/integration/test_cite.py` — **4 passed** on the real studionet,
  against the corrected source that was deployed.
- First run: 2 failed with a `502 Bad Gateway` from the hosted RPC; a retry
  passed all four tests, so the failures were transient, not contract logic.

## 7. Deploy and revision

- Corrected source deployed to studionet.
- New contract address: `0x00E02cD320768cd8E55ac7C786119F76BD7452BB`.
- Updated `deployments.json`, `frontend/.env.local`, rebuilt frontend.
- Committed and pushed: `4cad7286f049e385882d5f1f32433ad5d10d15cc`.

Corrected GitHub revision:
https://github.com/weels007/cite/commit/4cad7286f049e385882d5f1f32433ad5d10d15cc
