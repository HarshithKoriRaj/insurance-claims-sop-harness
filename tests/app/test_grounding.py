from pathlib import Path

from app.conversation.interpretation import IdentityMention, Interpretation
from app.conversation.service import grounded
from app.workflow.state import CaseHints

ROOT = Path(__file__).resolve().parents[2]


def test_hints_the_caller_never_said_are_dropped():
    text = "I'm calling about my denied healthcare claim from January"
    model = Interpretation(case_hints=CaseHints(case_type="healthcare", status="denied", month=1, year=2025, case_id="POL-9921"))
    hints = grounded(model, text, False).case_hints
    assert (hints.case_type, hints.status, hints.month, hints.year, hints.case_id) == ("healthcare", "denied", 1, None, None)


def test_a_stated_case_id_and_year_are_kept():
    hints = grounded(Interpretation(case_hints=CaseHints(case_id="CL-2048", year=2026, month=1)), "claim CL-2048 from January 2026", False).case_hints
    assert (hints.case_id, hints.year, hints.month) == ("CL-2048", 2026, 1)


def test_identity_values_must_appear_in_the_message():
    text = "My name is Margaret Chen, DOB is 1985-03-15"
    model = Interpretation(identity=IdentityMention(full_name="Margaret Chen", dob="1985-03-15", email="margaret@email.com", ssn_last4="4472"))
    identity = grounded(model, text, False).identity.present()
    assert identity == {"full_name": "Margaret Chen", "dob": "1985-03-15"}


def test_a_reformatted_value_falls_back_to_the_rule_reading():
    text = "I was born March 15, 1985"
    identity = grounded(Interpretation(identity=IdentityMention(dob="1985-03-15")), text, False).identity.present()
    assert identity == {"dob": "March 15, 1985"}


def test_the_committed_env_template_holds_no_real_key():
    template = (ROOT / ".env.example").read_text()
    for line in template.splitlines():
        if line.startswith(("OPENAI_API_KEY=", "ANTHROPIC_API_KEY=")):
            assert line.split("=", 1)[1].strip() == "", "a real key must never be committed in .env.example"
