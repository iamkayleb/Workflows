## Why
Any merchant API can be read or written by an anonymous caller who supplies a
tenant id in a header. No sign-in required.

    curl -H "x-tenant-id: cmw93dvh50000tb78x6gf22xi" https://host/api/services

`runForTenant` in `app/api/services/_helpers.ts` resolves the tenant through
`resolveTenant`, which tries the session first and then falls back to the
`x-tenant-id` header and the host subdomain. Issue #542 made the session win
when one is present; it did not remove the path that needs no session at all.

Tenant ids are not secret. One was rendered in the merchant header until #547,
`serializeService` returns `tenantId` in every response, and ids appear in
error payloads. Anyone who has seen one can read that tenant's services,
business hours and bookings, and can write to them.

This was found by the agent working #546, which flagged it against its own
change rather than shipping quietly.

## Scope
Merchant APIs require a signed-in session. The header and subdomain paths stop
being an authentication bypass.

## Non-Goals
No change to the public surface: `app/api/public/bookings/route.ts` and the
`/{slug}` pages resolve a tenant from the URL on purpose and expose only public
data. No new auth scheme, no roles or permissions — only "is there a valid
session, and does it own this tenant".

## Tasks
- [ ] In `app/api/services/_helpers.ts`, change `runForTenant` to resolve the tenant from the session alone and return HTTP 401 when there is no valid session.
- [ ] In `app/api/services/_helpers.ts`, return HTTP 403 when a session exists but names a different tenant from an `x-tenant-id` header, rather than silently preferring one.
- [ ] In `app/lib/resolve-tenant.ts`, add a `requireSession` option so the public callers keep the slug path and the merchant callers cannot reach it.
- [ ] Update `app/api/business-hours/route.ts` and `app/api/bookings/route.ts` to use the session-only path, once #546 and #544 have merged.
- [ ] Add `__tests__/app/api/auth/tenant-isolation.test.ts` covering: a header with no session returns 401, a session returns that tenant's rows, a session plus a conflicting header returns 403, and a public booking by slug still succeeds.
- [ ] Record the change in `docs/` or the repository README so the next route author does not reintroduce the fallback.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] Against a real database with `pnpm prisma migrate deploy` and `pnpm db:seed` run, `GET /api/services` with an `x-tenant-id` header and no session cookie returns 401 and no service data.
- [ ] The same request with a valid session cookie and no header returns 200 and that tenant's three seeded services.
- [ ] A request with a valid session for one tenant and an `x-tenant-id` header naming another returns 403.
- [ ] `POST /api/public/bookings` with a valid `slug` and no session still returns 201, proving the public path is untouched.
- [ ] `grep -rn "x-tenant-id" app/api/` shows the header read only where a session has already been required.

## Implementation Notes
`resolveTenant` already returns a `source` field of `session`, `header`,
`subdomain` or `none`. The simplest correct change is for the merchant path to
accept only `source === "session"`.

Check what depends on the header before removing it — `eval/smoke.mjs` uses it,
and that script will need a session instead.
