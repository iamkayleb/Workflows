#!/usr/bin/env python3
"""Apply to work.py: adopt a pull request the agent opened instead of dying.

    python adopt-existing-pr.py

The prompt tells the agent not to open a pull request, because the harness
controls branch naming and review state. Cursor opened one anyway. The round
then pushed its commit, called POST /pulls, got

    gh: Validation Failed (HTTP 422)

and died at the last step with the work already on the remote.

An agent ignoring an instruction is a fact about the world, not a bug to argue
with. So: look first, adopt what is there, and only create when nothing exists.
The round still reports honestly which of the two happened, because a harness
that quietly tolerates being overruled stops being a control.

Safe to run more than once.
"""
from __future__ import annotations

import pathlib
import sys

p = pathlib.Path("work.py")
if not p.exists():
    sys.exit("work.py not found — run this from bukay-ops")
s = p.read_text(encoding="utf-8").replace("\r\n", "\n")

if "already opened a pull request" in s:
    print("already applied")
    raise SystemExit(0)

start = s.find('        pr = run(["gh", "api", "-X", "POST", f"repos/{REPO}/pulls",')
if start == -1:
    sys.exit("could not find the pull request creation — send me work.py")
end = s.find('print("outcome to record: new_issue")', start)
if end == -1:
    sys.exit("could not find the end of the publish block — send me work.py")

new = '''        # The agent is told not to open a pull request. If it did anyway,
        # adopt it rather than failing: the work is already pushed, and a round
        # that dies here loses nothing but the record of what it achieved.
        found = run(["gh", "api",
                     f"repos/{REPO}/pulls?state=open&head={REPO.split('/')[0]}:{branch}"],
                    timeout=120, check=False)
        existing = []
        try:
            existing = json.loads(found.stdout or "[]")
        except json.JSONDecodeError:
            existing = []

        if existing:
            url = existing[0]["html_url"]
            print(f"\\n{agent} already opened a pull request, against the "
                  f"instruction not to: {url}")
            print("adopting it rather than creating a second one")
        else:
            body = (f"Closes #{number}\\n\\n"
                    f"Opened by the local {agent} opener lane, round "
                    f"`{claim['round_id']}`.\\n"
                    f"{n} commit(s) on top of `{BASE_BRANCH}` at {base_sha[:10]}.")
            pr = run(["gh", "api", "-X", "POST", f"repos/{REPO}/pulls",
                      "-f", f"title={iss['title']}",
                      "-f", f"head={branch}",
                      "-f", f"base={BASE_BRANCH}",
                      "-f", f"body={body}",
                      "-F", f"draft={'true' if OPEN_AS_DRAFT else 'false'}"],
                     timeout=120)
            url = json.loads(pr.stdout)["html_url"]
        print(f"\\npull request: {url}")
        '''
s = s[:start] + new + s[end:]
p.write_text(s, encoding="utf-8", newline="\n")
print("applied: adopt an existing pull request instead of failing on 422")
