#!/usr/bin/env python3
"""End-to-end story: five short customer conversations against a running Claims
Assistant (local Docker or the live demo), checking what each phase must and must
not do. Standard library only.

    python3 scripts/story.py                                        # http://localhost:8000
    python3 scripts/story.py https://claims-assistant-4wy7.onrender.com

Checks use the session state the API returns (phase, verification, selected claim,
counters) plus the facts a reply must contain, so they hold whatever wording the
model chooses. Exit code 0 means every check passed."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
LEAKS = re.compile(r"CL-?\s?\d{4}|\$\s?\d|pathology|office note|March 18|2026-03-18", re.IGNORECASE)
failures: list[str] = []


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + "/api" + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"HTTP {error.code} from {path}: {error.read().decode()[:200]}") from None


class Conversation:
    def __init__(self, title: str) -> None:
        print(f"\n=== {title}")
        created = request("POST", "/sessions")
        self.sid, self.token, self.view = created["session_id"], created["token"], created["view"]

    def say(self, text: str) -> dict:
        print(f"\n  You: {text}")
        self.view = request("POST", f"/sessions/{self.sid}/messages", {"text": text}, self.token)["view"]
        self._show()
        return self.view

    def act(self, action: str) -> dict:
        print(f"\n  [clicks {action}]")
        self.view = request("POST", f"/sessions/{self.sid}/actions", {"action": action}, self.token)["view"]
        self._show()
        return self.view

    def _show(self) -> None:
        reply = self.reply.replace("\n", " ")
        print(f"  Assistant ({self.view['phase']}): {reply[:220]}{'...' if len(reply) > 220 else ''}")

    @property
    def reply(self) -> str:
        return self.view["messages"][-1]["text"]

    @property
    def verified(self) -> bool:
        return self.view["verification"]["verified"]

    @property
    def case(self) -> str | None:
        return (self.view["selected_case"] or {}).get("case_id")


def check(label: str, condition: bool) -> None:
    print(f"    {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        failures.append(label)


health = request("GET", "/health")
print(f"Target {BASE}: model mode {health['model_mode']} ({health['model']})")

# 1. Margaret: all four phases, memory across phases, no disclosure before verification.
c = Conversation("Story 1: Margaret Chen and her denied claim (all four phases)")
check("starts in VERIFY_ID, not verified", c.view["phase"] == "VERIFY_ID" and not c.verified)
c.say("What is RL?")
check("off-topic question is declined and counted", c.view["recovery"]["off_topic"] == 1 and c.view["phase"] == "VERIFY_ID")
c.say("My name is Margaret Chen. I'm calling about my denied healthcare claim from January.")
check("still not verified after one detail", not c.verified and c.view["verification"]["fields_provided"] == ["full_name"])
check("the claim hint is remembered before verification",
      c.view["memory"]["case_hints"]["status"] == "denied" and c.view["memory"]["case_hints"]["month"] == 1)
check("nothing about any claim is disclosed yet", not LEAKS.search(c.reply))
c.say("My date of birth is 1985-03-15.")
check("two details are still not enough", not c.verified and len(c.view["verification"]["fields_provided"]) == 2)
check("still nothing disclosed", not LEAKS.search(c.reply))
c.say("SSN last four is 4472.")
check("verified from name, date of birth and SSN last 4", c.verified)
check("the remembered hint selects CL-2048 without asking which claim", c.case == "CL-2048" and c.view["phase"] == "PROCESS_CASE")
check("the answer names CL-2048 and its appeal deadline (17 days from 2026-03-01)",
      "CL-2048" in c.reply and "17" in c.reply)
c.say("This is so frustrating. What if I can't get the pathology report?")
check("the follow-up stays on CL-2048", c.case == "CL-2048")
check("the reply offers the approved alternative (a replacement or supporting records)",
      re.search(r"replacement|supporting records|alternative", c.reply, re.IGNORECASE) is not None)
c.say("What about claim CL-3001?")
check("another customer's claim is not found and nothing about it is shown",
      c.case is None and not re.search(r"April 15|2026-04-15", c.reply))
c.say("OK, back to the denied one.")
check("the caller can pick CL-2048 again", c.case == "CL-2048")
c.say("That's all, thanks.")
check("wrap-up offers the email summary", c.view["phase"] == "POST_PROCESS" and c.view["summary"]["status"] == "offered")
summary = c.view["summary"]
check("the preview goes to the masked email on file and covers the claim",
      summary["recipient"] == "m*******@email.com" and "CL-2048" in summary["body"] and "2026-03-18" in summary["body"])
c.act("send_summary")
check("the summary is sent once and the conversation closes",
      c.view["summary"]["status"] == "sent" and c.view["lifecycle"] == "CLOSED")
print(f"    info  delivered to a mail inbox: {c.view['summary']['delivered']} "
      "(true with Docker Compose + Mailpit, false on the live demo)")

# 2. Wrong details: every attempt counts, and three failures stop automated verification.
c = Conversation("Story 2: someone guessing Margaret's SSN")
for attempt, guess in enumerate(("1111", "2222"), start=1):
    c.say(f"My name is Margaret Chen, DOB 1985-03-15, SSN last four {guess}.")
    check(f"attempt {attempt} fails without saying which detail was wrong",
          not c.verified and c.view["verification"]["failed_attempts"] == attempt and not LEAKS.search(c.reply))
c.say("My name is Margaret Chen, DOB 1985-03-15, SSN last four 3333.")
check("the third failure hands off to a human", c.view["lifecycle"] == "HANDOFF_PENDING")
c.say("My name is Margaret Chen, DOB 1985-03-15, SSN last four 4472.")
check("even correct details no longer verify in a locked session", not c.verified)

# 3. Fixture trap: Ma Tian holds a national ID, which never counts as an SSN.
c = Conversation("Story 3: Ma Tian and a national ID")
c.say("My name is Ma Tian, DOB 1964-09-10, SSN last four 6688.")
check("a national ID number is not accepted as an SSN", not c.verified)
c.say("My name is Ma Tian, born 1964-09-10, phone (650) 208-8799.")
check("name, date of birth and phone verify her", c.verified)
check("she sees only her own claim", "CL-3001" in c.reply and "CL-2048" not in c.reply)

# 4. Refusal and a human: explain, offer alternatives, then escalate without claiming a connection.
c = Conversation("Story 4: a caller who won't share details")
c.say("Why do you need my SSN? I don't want to give it.")
check("the refusal is counted and explained", c.view["recovery"]["refusals"] == 1 and not c.verified)
c.say("I'm not comfortable sharing any of that.")
check("a second refusal is counted", c.view["recovery"]["refusals"] == 2)
c.say("Please connect me to a human.")
check("a human is requested, not reported as connected",
      c.view["lifecycle"] == "HANDOFF_PENDING" and re.search(r"request", c.reply, re.IGNORECASE) is not None)

# 5. No guessing: an ambiguous date is asked about, and two similar claims are asked about.
c = Conversation("Story 5: an ambiguous date and two January claims")
c.say("My name is Margaret Chen, DOB 03/04/1985.")
check("03/04/1985 is not guessed: only the name is accepted", c.view["verification"]["fields_provided"] == ["full_name"])
check("the reply asks March 4 or April 3", "March 4" in c.reply and "April 3" in c.reply)
c.say("My name is Margaret Chen, born March 15, 1985, email margaret@email.com.")
check("verified with name, date of birth and email", c.verified and c.view["phase"] == "RESOLVE_INTENT")
c.say("It's about my healthcare claim from January.")
check("two January healthcare claims: the assistant asks which one",
      c.case is None and "CL-2048" in c.reply and "CL-2011" in c.reply)
c.say("The denied one.")
check("the denied one is CL-2048", c.case == "CL-2048")

print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED:'}")
for label in failures:
    print(f"  - {label}")
sys.exit(1 if failures else 0)
