## Why
The merchant header shows a raw database id — `cmw93dvh50000tb78x6gf22xi` —
where the business name should be. `SessionPayload` carries `tenantId` but no
name or slug, so `app/(app)/layout.tsx` falls through its
`tenantSlug ?? tenantId` chain to the id.

It is the first thing a merchant sees after signing in.

## Scope
Show the tenant's actual name in the header.

## Non-Goals
No logo, no branding colours, no tenant switcher. One string in one place.

## Tasks
- [ ] In `app/(app)/layout.tsx`, look the tenant up by the resolved `tenantId` and render `tenant.name`.
- [ ] In `app/(app)/layout.tsx`, fall back to the slug and then to "Bukay" when no tenant row matches. A session whose tenant was deleted must not crash the layout.
- [ ] Add `__tests__/app/(app)/layout-tenant-name.test.tsx` asserting the name is rendered for a seeded tenant and that a missing tenant falls back without throwing.

## Acceptance Criteria
- [ ] `pnpm build` and `pnpm vitest run` pass with no new failures.
- [ ] With a seeded database, the layout renders "Bukay Demo Salon" for the demo tenant, verified against a real database rather than a mock.
- [ ] A merchant signs in, opens `/services`, and sees "Bukay Demo Salon" in the header instead of an id beginning `cm`.
- [ ] No page under `app/(app)/` renders a string matching `^cm[a-z0-9]{20,}$`.

## Implementation Notes
`model Tenant` has both `name` and `slug`. Prefer `name` — the slug is a URL
segment, not a display string. The lookup is one query in a layout that already
runs per request.
