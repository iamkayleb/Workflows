## Why
A customer phones to book and the merchant has no way to enter it. This is the
single most common thing a salon owner does all day, and the application cannot
do it — bookings can only arrive through the public page.

## Scope
A "New booking" form on `/calendar` that creates a booking for an existing or
new client, honouring the same availability and conflict rules as the public
flow.

## Non-Goals
No recurring bookings, no staff assignment, no payment taken at entry. A
merchant-entered booking is created as `confirmed` and unpaid.

## Tasks
- [ ] Add `POST` to `app/api/bookings/route.ts` accepting `serviceId`, `startsAt`, `clientId` or a new client's `name` and `phone`, and optional `notes`.
- [ ] Reuse `computeSlots` from `app/lib/availability.ts` to reject a time outside business hours with HTTP 422.
- [ ] In `app/api/bookings/route.ts`, reject a time overlapping an existing booking for the same service with HTTP 409, matching the public flow in `app/api/public/bookings/route.ts`.
- [ ] Create the client when `phone` is given and no `clientId` matches, respecting the `@@unique([tenantId, phone])` constraint on `model Client`.
- [ ] Add `app/(app)/calendar/new-booking-form.tsx` with service, date, time, client-or-new-client and notes fields, following the conventions in `app/(app)/services/service-form.tsx`.
- [ ] Render that form on `app/(app)/calendar/page.tsx` below the day list.
- [ ] Add `__tests__/app/api/bookings/create.test.ts` covering a successful create, the out-of-hours rejection, the overlap conflict and tenant scoping, against a real database.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] With `pnpm prisma migrate deploy` on an empty database and `pnpm db:seed` run, `POST /api/bookings` with a valid service and a 2026-06-16T10:00 start returns 201 and the row is present. This must run against a real database, not a mock.
- [ ] Posting the same service and time twice returns 409 the second time.
- [ ] Posting a time outside the seeded Mon–Sat 09:00–18:00 hours returns 422.
- [ ] A merchant signs in, opens `/calendar`, adds a booking for a new client called Tunde on 16 June 2026 at 10:00, and sees it listed on that date after a reload.

## Implementation Notes
`model Booking` requires `endsAt`; compute it from the service's
`durationMinutes`. Set `status` to `"confirmed"`. Leave `slotLock` null —
that field belongs to the public flow's ten-minute hold.
