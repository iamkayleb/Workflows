## Why
`/today` is the first screen a merchant sees after signing in, and it is a bare
list of appointments. It answers "who is coming" and nothing else — not how
many, not how much, not what is still unpaid.

## Scope
Three figures at the top of `/today`: bookings today, money taken today, and
bookings still unpaid.

## Non-Goals
No charts, no comparisons with yesterday, no date picker. Three numbers for the
current day in the tenant's timezone.

## Tasks
- [ ] In `app/(app)/today/data.tsx`, add a function returning the count of today's bookings, the sum of `amountCents` for payments with status `paid` created today, and the count of today's bookings with no paid payment.
- [ ] Use the existing `zonedDayRange` in `app/(app)/today/data.tsx` for the day boundary so the figures match the list below them.
- [ ] Add `app/(app)/today/summary.tsx` rendering the three figures with labels.
- [ ] Render it above the appointment list in `app/(app)/today/data.tsx`.
- [ ] Add `__tests__/app/(app)/today/summary.test.ts` covering a day with bookings and payments, an empty day, and the timezone boundary, against a real database.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] With a seeded database and a booking created for today, the summary function returns a count of 1. This must run against a real database, not a mock.
- [ ] On a day with no bookings the three figures read zero rather than the section being absent.
- [ ] A booking whose payment status is `pending` counts toward unpaid, not toward money taken.
- [ ] A merchant signs in, adds a booking for today through `/calendar`, opens `/today`, and sees the booking count rise by one.

## Implementation Notes
The seeded booking is dated 15 June 2026, so today's figures will read zero on
a fresh seed. That is correct. Create a booking for today through `/calendar`
to see non-zero values — which is what the last criterion asks for.
