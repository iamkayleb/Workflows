#!/usr/bin/env python3
"""Apply to work.py: add `--repeat N` to probe, and per-agent timeouts.

    python probe-repeat.patch.py work.py
"""
import pathlib, sys

p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "work.py")
s = p.read_text(encoding="utf-8")

# 1. --repeat, so flakiness becomes a number instead of an impression
old = '''    names = [args.agent] if args.agent else list(ADAPTERS)
    worst = 0
    for name in names:
        b = find_bin(name)
        print(f"\\n  {name}: {b or 'NOT FOUND — skipping'}")
        if not b:
            continue
        try:
            worst = max(worst, _probe_one(name, b, args))
        except Exception as exc:                       # noqa: BLE001
            # One agent's mess must not abort the others. Windows in
            # particular refuses to delete a temp directory while a child
            # process still holds a handle on it.
            print(f"    ** probe raised {type(exc).__name__}: {exc}")
            worst = max(worst, 2)
    return worst'''
new = '''    names = [args.agent] if args.agent else list(ADAPTERS)
    worst = 0
    for name in names:
        b = find_bin(name)
        print(f"\\n  {name}: {b or 'NOT FOUND — skipping'}")
        if not b:
            continue
        results = []
        for attempt in range(args.repeat):
            if args.repeat > 1:
                print(f"    --- attempt {attempt + 1}/{args.repeat}")
            try:
                r = _probe_one(name, b, args)
            except Exception as exc:                   # noqa: BLE001
                # One agent's mess must not abort the others. Windows in
                # particular refuses to delete a temp directory while a child
                # process still holds a handle on it.
                print(f"    ** probe raised {type(exc).__name__}: {exc}")
                r = 2
            results.append(r)
            worst = max(worst, r)
        if args.repeat > 1:
            ok = sum(1 for r in results if r == 0)
            print(f"    => {ok}/{args.repeat} clean "
                  f"({100 * ok // args.repeat}%)  codes={results}")
    return worst'''
assert old in s, "probe loop not found — is this the current work.py?"
s = s.replace(old, new)

s = s.replace('''    pp.add_argument("--timeout", type=int, default=90,''',
'''    pp.add_argument("--repeat", type=int, default=1,
                    help="run each agent N times; prints a success rate")
    pp.add_argument("--timeout", type=int, default=90,''')

# 2. per-agent timeout, so one agent that hangs cannot eat the evening window
s = s.replace('''AGENT_TIMEOUT_SECONDS = int(os.environ.get("BUKAY_AGENT_TIMEOUT", "2100"))  # 35 min''',
'''AGENT_TIMEOUT_SECONDS = int(os.environ.get("BUKAY_AGENT_TIMEOUT", "2100"))  # 35 min

# A per-agent override. An agent that sometimes hangs should not be able to
# consume the whole evening window before the harness gives up on it: with a
# 4.5-hour window and a ceiling of six rounds, one 35-minute hang costs more
# than the round it wasted. Set e.g. BUKAY_CURSOR_TIMEOUT=900.
def agent_timeout(agent: str) -> int:
    return int(os.environ.get(f"BUKAY_{agent.upper()}_TIMEOUT",
                              AGENT_TIMEOUT_SECONDS))''')
s = s.replace('''        print(f"\\nrunning {agent} (timeout {AGENT_TIMEOUT_SECONDS}s)...\\n")''',
              '''        tmo = agent_timeout(agent)
        print(f"\\nrunning {agent} (timeout {tmo}s)...\\n")''')
s = s.replace('''                            timeout=AGENT_TIMEOUT_SECONDS,''',
              '''                            timeout=tmo,''')

p.write_text(s, encoding="utf-8")
print(f"patched {p}")
