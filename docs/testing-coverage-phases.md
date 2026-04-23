# Test Coverage Phases

This plan turns the current testing gaps into executable phases with clear completion gates.

## Execution Status

- Completed on 2026-04-23:
  - Phase 1 backend coverage additions:
    - `apps/matching/tests/test_ring_detector.py` added `retry_ring_after_decline` integration coverage.
    - `apps/matching/tests/test_matching.py` added ring decline enqueue-failure behavior test and `_notify_ring_cancelled` helper coverage.
  - Phase 1 frontend verification:
    - Targeted tests pass for Matches, Trades, TradeDetail, Proposals, Donations page suites.
  - Phase 2 initial additions:
    - `apps/trading/tests/test_trading_tasks.py` added explicit CONFIRMED auto-close shipment-status regression lock.
    - `apps/accounts/tests/test_usps_service.py` added USPS token cache, 401 retry, and malformed response coverage.
  - Phase 3 additions:
    - `apps/matching/tests/test_preference_filters.py` added dedicated `wishlist_allows_book` unit tests for accented titles, mixed-case authors, and NOT-abridged phrasing.
    - `apps/matching/services/preference_filters.py` now treats explicit non-abridged phrasing as non-abridged.
    - `apps/matching/tests/test_direct_matcher_duplicates.py` added dedicated `_duplicate_match_exists` direction/asymmetry-focused unit coverage.
  - Phase 4 additions:
    - `apps/accounts/tests/test_auth_api.py` added `/auth/logout/` refresh-token blacklist test.
    - `apps/accounts/tests/test_auth_api.py` added `/users/me/export/` structure-focused snapshot-like coverage.
    - `apps/notifications/tasks.py` now excludes institutional users from inactivity warning/delisting pipeline.
    - `apps/notifications/tests/test_tasks.py` added institutional inactivity exclusion test.
    - `apps/notifications/tests/test_tasks.py` added verification-email HTML username escaping test.

- Remaining:
  - Execute Phases 5 through 7.

Notes:
- In this environment, focused Django test runs may require `--reuse-db` if another session is holding the test database.

## Phase 1 - Contract and Critical Regression Coverage (Highest Priority)

Goal: prevent UI and workflow regressions caused by serializer shape drift and untested trade/match edges.

Scope:
- Frontend response-shape refactor in page tests so mocks match backend serializer payloads:
  - `frontend/src/pages/Matches*`
  - `frontend/src/pages/Trades*`
  - `frontend/src/pages/TradeDetail*`
  - `frontend/src/pages/Proposals*`
  - `frontend/src/pages/Donations*`
- Ring retry integration test for decline flow:
  - `apps/matching/services/ring_detector.py`
- MatchDeclineView failure/notification path coverage:
  - `apps/matching/views.py`

Required tests:
- Add integration test: 3-leg ring -> decline -> retry path verified.
- Add view test for `retry_ring_after_decline` returning `None` and assert `_notify_ring_cancelled` path fires.
- Refactor page mocks to actual API shapes (`results`, nested serializer fields, actionable codes/urls where applicable).

Exit gate:
- All updated page tests pass with real serializer shape mocks.
- New matching integration/view tests pass.
- No regressions in existing matching/trading test suites.

## Phase 2 - Async Task and External Service Reliability

Goal: lock down background job correctness and USPS service behavior under failures.

Scope:
- Trading task coverage:
  - `apps/trading/tasks.py`
- USPS service coverage:
  - `apps/accounts/services/usps.py`

Required tests:
- Add dedicated tests for:
  - `send_rating_reminders`
  - `auto_close_trades` (including confirmed auto-close bug regression case)
- Add USPS tests using `requests_mock` for:
  - token cache hit/miss behavior
  - 401 retry flow with token refresh
  - malformed/non-JSON USPS responses

Exit gate:
- New task tests are deterministic and isolated.
- USPS tests verify retries, cache behavior, and safe error handling.

## Phase 3 - Matcher and Filtering Edge Cases

Goal: prevent subtle false positives/negatives in matching and duplicate detection.

Scope:
- Preference filtering:
  - `apps/matching/services/preference_filters.py`
- Direct matcher duplicate branch:
  - `apps/matching/services/direct_matcher.py`

Required tests:
- Add dedicated unit tests for `wishlist_allows_book`:
  - accented titles
  - mixed-case authors
  - false-positive avoidance around "NOT abridged"
- Add direction-asymmetry regression tests for `_duplicate_match_exists`.

Exit gate:
- Edge-case text normalization and duplicate-direction behavior are explicitly locked by tests.

## Phase 4 - Auth, Privacy, and Policy Safeguards

Goal: close security/compliance policy gaps.

Scope:
- Logout and token blacklist:
  - `apps/accounts/tests/test_auth_api.py`
- GDPR export shape:
  - `apps/accounts/views.py`
- Notification policy exclusions:
  - `apps/notifications/tasks.py`
- Email escaping:
  - `apps/notifications/email.py`

Required tests:
- Add `TestLogoutView` for `/auth/logout/` and blacklist behavior.
- Add structure-focused export test for `_build_user_export`.
- Add edge-case test that institutional users are excluded from inactivity warnings.
- Add test for HTML escaping of untrusted usernames in emails.

Exit gate:
- Auth/session termination and policy behavior are covered.
- Privacy/export structure is validated and stable.

## Phase 5 - Inventory/Workflow Branches and Test Infra Cleanup

Goal: cover remaining business-rule branches and reduce test setup duplication.

Scope:
- Partner-only visibility rule:
  - `apps/inventory/tests/test_inventory_api.py`
- Trade workflow invalid branch:
  - `apps/trading/services/trade_workflow.py`
- Common fixture cleanup:
  - `conftest.py`

Required tests and cleanup:
- Add PartnerBooksView tests for confirmed partners vs outsiders.
- Add validation branch test for two proposal items in same direction -> `ValueError`.
- Add reusable `address_verified_user` fixture and migrate existing tests to it.

Exit gate:
- Remaining domain branches are covered.
- Repeated address verification setup is removed from per-test boilerplate.

## Phase 6 - Frontend Auth Concurrency and Hook Logic

Goal: lock down auth behavior under parallel failures and account-type logic.

Scope:
- API interceptor queue:
  - `frontend/src/services/api.test.js`
- Auth hook account-type flags:
  - `frontend/src/hooks/useAuth.test.jsx`

Required tests:
- Add concurrency test for two simultaneous 401 responses sharing one refresh request (`isRefreshing` queue semantics).
- Add parametrized `isInstitution` tests for `individual`, `library`, and `bookstore`.

Exit gate:
- Token refresh queue behavior is stable under parallel requests.
- Account-type derived flags are fully covered.

## Phase 7 - Full Pipeline Slow Integration

Goal: validate end-to-end business workflow across matching, trading, and ratings.

Scope:
- Cross-cutting integration path across matching/trading/ratings.

Required test:
- One slow integration test for:
  - accept match -> trade created -> both parties mark shipped -> both mark received -> ratings submitted -> average recomputed.

Exit gate:
- Workflow passes end-to-end with persisted state transitions verified at each step.

## Suggested Execution Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7

## Validation Commands

Backend targeted:
- `python -m pytest -q apps/matching apps/trading apps/accounts apps/notifications apps/inventory`

Frontend targeted:
- `cd frontend && npm run test:run -- src/pages src/services/api.test.js src/hooks/useAuth.test.jsx`

Final check:
- `python -m pytest -q`
- `cd frontend && npm run test:run`
