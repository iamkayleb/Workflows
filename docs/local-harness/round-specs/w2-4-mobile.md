## Why
The merchants this is built for run their business from a phone. Every merchant
screen was laid out at desktop width and none has been checked at phone width.
A demo on a handset is the first thing anyone will try.

## Scope
Make the six merchant screens usable at 390 pixels wide — no sideways scrolling
and no control pushed off the edge.

## Non-Goals
No redesign, no new components, no navigation pattern change. Layout only, at
one breakpoint.

## Tasks
- [ ] In `app/(app)/components/app-shell.tsx`, ensure the sidebar collapses rather than forcing a minimum page width at 390 pixels.
- [ ] In `app/(app)/calendar/day-view.tsx`, stack each booking's details vertically below 640 pixels instead of placing them in one row.
- [ ] In `app/(app)/services/services-list.tsx`, stack the duration, buffer, price and status rather than laying them out horizontally below 640 pixels.
- [ ] In `app/(app)/payments/payments-list.tsx`, do the same for the payments table once that file exists.
- [ ] In `app/(app)/settings/business-hours-form.tsx`, stack each day's opening time, closing time and closed toggle below 640 pixels.
- [ ] Add `__tests__/app/(app)/mobile-layout.test.tsx` rendering each merchant page and asserting that no element carries a fixed width greater than 390 pixels.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] With a seeded database and the app running, each of `/today`, `/calendar`, `/clients`, `/services`, `/settings` and `/payments` renders with `document.scrollWidth` equal to `window.innerWidth` at a viewport 390 pixels wide.
- [ ] A merchant opens `/calendar` in a browser window 390 pixels wide, reads a booking's client name, service and time, and reaches its controls without scrolling sideways.
- [ ] No merchant page hides its primary action off-screen at that width.

## Implementation Notes
Tailwind is already configured; `sm:` is 640 pixels and the existing pages use
it. Follow that convention rather than introducing new breakpoints.

390 pixels is an iPhone at its common logical width, and narrower than most
Android handsets, so it is the right floor to test against.
