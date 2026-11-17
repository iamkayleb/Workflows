## Why
A merchant who signs up for the first time lands on an empty `/today` with no
indication of what to do. Their tenant has no services and no business hours,
so their public booking page offers nothing and cannot take a booking.

Nothing tells them that, and nothing points them at the two screens that fix it.

## Scope
A first-run checklist on `/today` that appears only while setup is incomplete,
linking to the two things that must be done.

## Non-Goals
No multi-step wizard, no forced redirects, no progress persisted to the
database. The checklist is derived from whether the data exists.

## Tasks
- [ ] Add `app/(app)/setup-status.ts` returning whether the tenant has at least one active service and at least one business-hour row that is not closed.
- [ ] Add `app/(app)/today/setup-checklist.tsx` showing two items — "Add your first service" linking to `/services`, and "Set your opening hours" linking to `/settings` — each marked done or not.
- [ ] Render the checklist at the top of `app/(app)/today/data.tsx`, above the summary, and only while either item is outstanding.
- [ ] In `app/(app)/today/setup-checklist.tsx`, show the tenant's public booking link at `/{slug}` once both items are done, so the merchant knows where to send customers.
- [ ] Add `__tests__/app/(app)/setup-status.test.ts` covering a tenant with neither, with one, and with both, against a real database.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] Against a real database, `setup-status` reports both items outstanding for a tenant with no services and no open hours.
- [ ] For the seeded demo tenant, which has three services and Mon–Sat hours, it reports both complete.
- [ ] A merchant signs in to a tenant with no services, opens `/today`, sees "Add your first service" outstanding, follows the link, creates a service, returns to `/today`, and sees that item marked done.
- [ ] The checklist is absent entirely for the seeded demo tenant.

## Implementation Notes
A new tenant is created on first phone sign-in by the round-15 signup path, so
this is reachable by signing in with an unrecognised number.

Derive the state from the data rather than storing a flag. A merchant who
deletes all their services should see the checklist return.
