## Why
`main` does not build. `pnpm build` fails with:

> Type error: Page "app/(app)/today/page.tsx" does not match the required types of a Next.js Page.

Every pull request that follows will show a red check until this is fixed, so
nothing downstream can be verified. The test suite passes and conformance
scored this file as delivered; neither measure asks whether the app compiles.

## Scope
Move the helpers out of the page module so `page.tsx` exports only what Next
allows, and point the existing test at their new home.

## Non-Goals
No change to what the Today screen shows or how it queries. This is a module
boundary fix, not a feature change. Do not rewrite the tests beyond their
import line.

## Tasks
- [ ] Create `app/(app)/today/data.ts` and move `TodayBooking`, `zonedDayRange`, `listTodaysBookings` and `TodaySchedule` into it unchanged.
- [ ] Reduce `app/(app)/today/page.tsx` to its default export plus `export const dynamic`, importing `TodaySchedule` from `./data`. A Next.js App Router page may only export `default`, `metadata`, `generateMetadata`, `dynamic`, `revalidate`, `generateStaticParams` and `fetchCache`.
- [ ] Update the import in `__tests__/app/(app)/today/page.test.tsx` to read from `@/app/(app)/today/data`.
- [ ] Check every other `page.tsx` and `layout.tsx` under `app/` for the same pattern, and move any non-permitted export out the same way.

## Acceptance Criteria
- [ ] `pnpm build` completes with no type errors. This is the criterion the round exists for.
- [ ] `pnpm vitest run` passes, and all three cases in `__tests__/app/(app)/today/page.test.tsx` still run rather than being deleted or skipped.
- [ ] With `pnpm prisma migrate deploy` applied to an empty database and `pnpm db:seed` run, a merchant signs in, opens `/today`, and sees the seeded booking listed with its client name and service name.
- [ ] No file matching `app/**/page.tsx` or `app/**/layout.tsx` exports a name outside the permitted set.

## Implementation Notes
The helpers were exported from the page so the test could import them. That is
the cause: a test reached into a module whose exports the framework constrains.
Keeping the page thin and the logic in a sibling module is the pattern to
follow everywhere else too.
