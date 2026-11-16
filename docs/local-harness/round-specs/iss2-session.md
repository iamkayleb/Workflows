## Why
Signing in does nothing for any merchant screen. `/calendar` says "Unable to
determine your business", and `/services` only works if the caller supplies an
`x-tenant-id` header by hand. A merchant who signs in on `localhost:3000` sees
no data anywhere.

`resolveTenant()` already supports sessions — it returns `source: "session"`
when given one. No caller ever passes one:

- `app/(app)/services/services-list.tsx:20` — headers only
- `app/(app)/layout.tsx:19` — headers only
- `app/api/services/_helpers.ts:49` — headers only

So resolution always falls through to the `x-tenant-id` header or a subdomain,
neither of which exists in ordinary use. The session cookie is minted at
sign-in and then never read.

## Scope
Read the session cookie on the server and pass it to `resolveTenant`, so a
signed-in merchant resolves to their own tenant without a header or a subdomain.

## Non-Goals
No change to how sessions are signed or verified; `app/lib/auth/session.ts` is
correct and stays as it is. No change to the header and subdomain paths, which
public and API callers still use. Do not merge the two `resolveTenant`
implementations in `app/lib/` and `app/tenancy/` — that is a separate round.

## Tasks
- [ ] Add `sessionFromCookies()` to `app/lib/auth/session.ts`, reading the cookie header with the existing `readSessionTokenFromCookieHeader` then `verifySession`, and returning the payload or null.
- [ ] In `app/(app)/services/services-list.tsx`, pass that payload as `session` in the `resolveTenant` call at line 20.
- [ ] In `app/(app)/layout.tsx`, do the same for the call at line 19.
- [ ] In `app/api/services/_helpers.ts`, do the same for `runForTenant` at line 49, keeping the existing header path as a fallback for callers that supply one.
- [ ] Add `__tests__/app/lib/auth/session-tenant.test.ts` covering a valid cookie resolving to its tenant, an absent cookie falling through to the header, and a tampered cookie resolving to nothing.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] With `pnpm prisma migrate deploy` on an empty database and `pnpm db:seed` run, a merchant signs in at `http://localhost:3000/login` with the seeded owner's phone, opens `/services`, and sees the three seeded services — with no `x-tenant-id` header and no subdomain.
- [ ] The same merchant opens `/calendar`, picks 15 June 2026, and sees the seeded booking with its client name and service name, instead of "Unable to determine your business".
- [ ] `GET /api/services` with a valid session cookie and no `x-tenant-id` header returns 200 and that tenant's services, run against a real database.
- [ ] A request carrying a session for one tenant and an `x-tenant-id` header for another returns only the session tenant's rows.

## Implementation Notes
The seed currently gives the demo owner an email but no phone, so no one can
sign in as the tenant owning the seeded data. Give that owner the phone
`+2348061778668` in `prisma/seed.ts` as part of this round, otherwise the
criteria above cannot be performed.

The last criterion matters more than it looks: a session and a conflicting
header must not let a caller read another tenant's data.
