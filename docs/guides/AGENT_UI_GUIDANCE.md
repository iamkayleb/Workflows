# Getting a clean, consistent interface out of a coding agent

> What to put in an agent's instructions so the UI it builds looks like one
> product, and what to check so the instruction actually held.

## Start from the evidence

A design system was synced into a consumer repo. Four months of automated
rounds later it had **zero references** in the application, while 279 source
files styled themselves with hand-picked greys — thirty-six uses of one border
shade, thirty-five of one text shade, none of them from the system.

Nobody ignored an instruction on purpose. There was no instruction, and nothing
asked. That is the thing to fix, in that order:

1. **Make the system reachable** through the tool the agent already uses.
2. **Say so, once, where the agent reads.**
3. **Check the result**, because an instruction an agent can quietly skip is
   indistinguishable from one it followed.

Prompting alone is step 2 of 3, and it is the weakest of the three.

## 1. Make it reachable

The CSS layer (`tokens.css` + `components.css`) assumes a project writes
`.panel` and `.kpi`. A Tailwind project does not. Until something connects the
two, "use the design system" asks an agent to abandon the idiom it is fluent in,
and it will not.

Two adapters ship with the system for exactly this:

| Adapter | For |
|---|---|
| `design-system/tailwind-preset.js` | Tailwind / React / Next |
| `design-system/ds_streamlit.py` | Streamlit |

With the preset wired in, the system's tokens *are* the utilities:

```jsx
<div className="bg-surface border border-default rounded-card p-card">
  <h2 className="font-heading text-ink">Today</h2>
  <p className="text-muted text-ds-sm">No bookings yet</p>
</div>
```

Switching `theme-air` to `theme-paper`, or adding `density-compact`, restyles
the whole app without touching a component. That is the payoff, and it is worth
stating in the prompt because it is the reason the constraint is not arbitrary.

## 2. What to put in the agent's instructions

Keep it short and concrete. Agents follow specifics and skim philosophy. This
belongs in `AGENTS.md` / `CLAUDE.md`, which every lane reads:

```markdown
## Interface work

This project has a design system in `design-system/`. Use it.

- Colour, radius, and type come from tokens: `bg-surface`, `bg-panel`,
  `text-ink`, `text-muted`, `border-default`, `accent`, `rounded-card`,
  `text-ds-sm`. The full set is in `design-system/tokens.css`.
- Never write a literal colour — no `#1e293b`, no `rgb(...)`, no
  `bg-slate-900`. If a shade you need does not exist, say so in the pull
  request rather than inventing one.
- Status uses the status tokens: `text-pos`, `bg-neg-weak`, `border-warn`.
- Empty, loading and error states are patterns, not bespoke markup. Read
  `design-system/PRESENTATION_PATTERNS.md` and use the pattern.
- To change the palette for this app, override the token in the app
  stylesheet loaded after `tokens.css`. Never fork `components.css` or the
  preset.

Run `python scripts/check_design_system.py --strict` before you finish.
```

Three things that matter about that wording:

- **It names the utilities.** "Use the design system" is advice; `bg-surface` is
  an instruction.
- **It says what to do when the system is insufficient** — report it, don't
  improvise. Without that line an agent that needs a missing shade will invent
  one silently, which is how the fragmentation started.
- **It ends with a command.** An agent that can check its own work usually does.

## 3. Check the result

`scripts/check_design_system.py` reports literal colours in source — hex, `rgb()`,
`hsl()`, and inline `style=` colour attributes — anywhere outside
`design-system/` itself.

```bash
python scripts/check_design_system.py                 # advisory
python scripts/check_design_system.py --strict        # fails the build
python scripts/check_design_system.py --changed-only  # just this PR's files
```

It is deliberately narrow. It does not police spacing or typography, because a
check that fires on everything gets ignored, and then the one thing that
visibly fragments a product goes with it.

### Its honest limit

It catches literal colours. It does **not** catch `bg-slate-900`, which is a
valid Tailwind utility that happens to bypass the system. That gap is closed by
the preset rather than by the checker: once the palette an agent reaches for is
the design system's, using Tailwind *is* using the system, and the remaining
literal-colour check covers the escape hatch.

If you want the stronger check, delete the default Tailwind palette in
`tailwind.config.js` so `slate-*` stops resolving at all. That is a real
refactor on an existing app and a one-line decision on a new one.

## Verifying how it *looks*, not just what it uses

The checks above prove a component asked for the right token. They do not prove
the page renders well. For that, the UI acceptance lane already drives a real
browser — so a presentation rule can be an acceptance criterion like any other:

```ts
test('[AC-6] the dashboard uses the design system surface, not an ad-hoc grey', async ({ page }) => {
  await page.goto('/app');
  const panel = page.getByTestId('today-panel');
  await expect(panel).toHaveCSS('background-color', 'rgb(250, 250, 250)'); // --panel
});
```

See `docs/guides/UI_ACCEPTANCE.md`. Use this sparingly: asserting computed
styles everywhere makes a brittle suite that fails on every token change. One or
two anchors per screen is enough to catch a component that went its own way.

## The order, restated

Reachable, then stated, then checked. A project that does only the middle one
gets what the evidence above describes: a design system in the repository, and a
product that does not use it.
