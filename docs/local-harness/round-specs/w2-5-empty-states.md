## Why
Every merchant screen shows a blank area when it has no data. A new merchant
sees five empty pages and cannot tell whether the app is broken, still loading,
or simply waiting for them to add something.

## Scope
Each merchant screen states what is missing and offers the action that fixes it.

## Non-Goals
No illustrations, no copywriting pass on existing text, no changes to screens
that have data. Empty states only.

## Tasks
- [ ] In `app/(app)/calendar/day-view.tsx`, when the chosen date has no bookings, show "No bookings on this date" with a link to add one.
- [ ] In `app/(app)/services/services-list.tsx`, when the tenant has no services, show "No services yet — add your first so customers can book" above the create form.
- [ ] In `app/(app)/clients/page.tsx`, when the tenant has no clients, show "No clients yet — they appear here after their first booking".
- [ ] In `app/(app)/payments/payments-list.tsx`, when there are no payments, show "No payments yet" once that file exists.
- [ ] In `app/(app)/today/data.tsx`, keep the existing "No appointments yet" message and link it to `/calendar` so the merchant can add one.
- [ ] Add `__tests__/app/(app)/empty-states.test.tsx` rendering each page with an empty tenant and asserting each message appears.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] Against a real database with a tenant that has no services, no clients and no bookings, each of the five pages renders its message rather than an empty region.
- [ ] None of those messages appears for the seeded demo tenant, which has data on every screen.
- [ ] A merchant signs in to an empty tenant, opens `/clients`, reads that clients appear after their first booking, and is not left looking at a blank page.
- [ ] `grep -rn "Nothing here yet" app/` returns nothing, confirming the old placeholder wording is gone.

## Implementation Notes
`app/(app)/components/section-placeholder.tsx` still exists for any page that
has not been rebuilt. If no page imports it after this round, delete it.
