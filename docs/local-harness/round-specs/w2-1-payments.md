## Why
A merchant cannot see any money they have taken. `model Payment` and
`model LedgerEntry` are fully modelled, both the Paystack and Flutterwave
webhooks write to them, and nothing in the merchant interface reads either.

For a booking business, "what have I been paid" is the second question after
"who is coming today".

## Scope
A payments list at `/payments`: every payment with its amount, status, date,
the client who paid and the service booked.

## Non-Goals
No refunds, no payouts, no provider reconciliation, no date-range filtering.
A readable list of what has happened.

## Tasks
- [ ] Add `app/api/payments/route.ts` with `GET` returning the tenant's payments ordered by `createdAt` descending, including the related booking's client name and service name.
- [ ] In `app/api/payments/route.ts`, accept an optional `status` query parameter and filter on it, rejecting an unknown value with HTTP 422.
- [ ] Add `app/(app)/payments/page.tsx` listing each payment with amount formatted from `amountCents`, status, date, client name and service name.
- [ ] Add `app/(app)/payments/payments-list.tsx` holding the table so the page stays a thin default export, matching the pattern in `app/(app)/today/data.tsx`.
- [ ] Add a "Payments" entry to `app/(app)/components/nav-items.ts` so the page is reachable.
- [ ] Show a total of paid amounts at the top of `app/(app)/payments/page.tsx`, summing only payments whose `status` is `paid`.
- [ ] Add `__tests__/app/api/payments/route.test.ts` covering ordering, the status filter, the 422, and tenant scoping, against a real database.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] With `pnpm prisma migrate deploy` on an empty database and `pnpm db:seed` run, `GET /api/payments` returns the seeded payment with its client and service names. This must run against a real database, not a mock.
- [ ] `GET /api/payments?status=banana` returns 422.
- [ ] A request carrying another tenant's session returns none of these rows.
- [ ] A merchant signs in, opens `/payments` from the navigation, and sees the seeded ₦50.00 payment listed as paid against Demo Client and Classic Haircut.

## Implementation Notes
`amountCents` is in the currency's smallest unit; divide by 100 for display,
as `formatPrice` already does in `app/(app)/services/services-list.tsx`.
Reuse that helper rather than writing a second one.

`status` values written by the webhooks are `pending` and `paid`; check
`app/lib/payments/` before inventing others.
