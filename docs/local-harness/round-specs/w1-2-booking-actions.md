## Why
A booking on `/calendar` can only be looked at. A merchant cannot cancel one,
move it, or record that the customer did not turn up — so the calendar drifts
out of step with reality by the end of the first day.

## Scope
Cancel, reschedule and mark-no-show, from the booking row on `/calendar`.

## Non-Goals
No refunds, no customer notification, no bulk actions. Those depend on the
payments and messaging surfaces and are separate rounds.

## Tasks
- [ ] Add `PATCH` to `app/api/bookings/[id]/route.ts` accepting `status` (one of `confirmed`, `cancelled`, `completed`, `no_show`) and optionally a new `startsAt`.
- [ ] Recompute `endsAt` from the service's `durationMinutes` whenever `startsAt` changes.
- [ ] In `app/api/bookings/[id]/route.ts`, reject a reschedule overlapping another booking for the same service with HTTP 409.
- [ ] In `app/api/bookings/[id]/route.ts`, return HTTP 422 for an unknown status. Return HTTP 404 for a booking belonging to another tenant.
- [ ] Standardise on the spelling `cancelled`. The codebase currently contains both `cancelled` (17 uses) and `canceled` (2); change the two to match the majority.
- [ ] Add cancel, reschedule and no-show controls to `app/(app)/calendar/day-view.tsx`, each confirming before it acts.
- [ ] Add `__tests__/app/api/bookings/update.test.ts` covering each transition, the overlap conflict, the unknown status and cross-tenant access, against a real database.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] With a seeded database, `PATCH /api/bookings/{id}` with `{"status":"cancelled"}` returns 200 and the stored row reads `cancelled`. This must run against a real database, not a mock.
- [ ] `PATCH` with `{"status":"maybe"}` returns 422 and the row is unchanged.
- [ ] Rescheduling onto a time already taken by another booking for the same service returns 409.
- [ ] A merchant signs in, opens `/calendar` on 15 June 2026, cancels the seeded booking, reloads, and sees it marked cancelled rather than confirmed.
- [ ] `grep -r "canceled" app/` returns nothing.

## Implementation Notes
`status` is a plain `String` on `model Booking` with no database constraint, so
validation belongs in the route. The public booking flow writes
`pending_payment`; leave that value alone.
