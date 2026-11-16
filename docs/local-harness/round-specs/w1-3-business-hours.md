## Why
`model BusinessHour` exists, the availability engine reads it, and the seed
writes it — but nothing in the application lets a merchant change it. The
settings page says so itself: "Additional settings (business hours, branding,
integrations) are not available yet."

A merchant who opens late on Mondays cannot say so, and the public booking page
will keep offering slots they cannot serve.

## Scope
A business-hours editor on `/settings`: seven rows, one per weekday, each with
opening time, closing time and a closed toggle.

## Non-Goals
No per-staff hours, no date-specific overrides for holidays, no lunch breaks.
One weekly pattern per tenant.

## Tasks
- [ ] Add `app/api/business-hours/route.ts` with `GET` returning the tenant's seven rows ordered by `dayOfWeek`, and `PUT` replacing them in one transaction.
- [ ] Validate that `opensAt` and `closesAt` are `HH:MM` strings and that opening is before closing, returning HTTP 422 otherwise.
- [ ] Treat a row with `isClosed` true as closed regardless of its times.
- [ ] Add `app/(app)/settings/business-hours-form.tsx` rendering seven rows, defaulting a missing day to closed.
- [ ] Render it on `app/(app)/settings/page.tsx` and remove the "not available yet" sentence.
- [ ] Add `__tests__/app/api/business-hours/route.test.ts` covering the replace, the validation failures and tenant scoping, against a real database.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] With `pnpm prisma migrate deploy` on an empty database and `pnpm db:seed` run, `GET /api/business-hours` returns the seeded Mon–Sat 09:00–18:00 rows. This must run against a real database, not a mock.
- [ ] `PUT` with `opensAt` of `18:00` and `closesAt` of `09:00` returns 422 and nothing is changed.
- [ ] A merchant signs in, opens `/settings`, marks Wednesday closed, saves, reloads, and still sees Wednesday closed.
- [ ] After that change, the public page at `/demo/book` offers no slots on a Wednesday.

## Implementation Notes
`@@unique([tenantId, dayOfWeek])` means a PUT should upsert by that pair rather
than delete-and-recreate, so existing ids survive. `dayOfWeek` is 0–6 with 0 as
Sunday, matching the seed.
