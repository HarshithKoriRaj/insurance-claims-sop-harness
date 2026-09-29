"""End-to-end workflow through the HTTP API, in offline mode (rule interpreter and
templates), so every assertion is deterministic."""

from datetime import timedelta

MARGARET = (
    "I'm the policyholder. My name is Margaret Chen, policy POL-9921. I'm calling about my denied "
    "healthcare claim from January. DOB is 1985-03-15, SSN last four is 4472."
)


def test_margaret_is_verified_and_routed_to_cl_2048_from_her_early_hint(chat):
    assert chat.view["phase"] == "VERIFY_ID"
    reply = chat.say(MARGARET)
    view = chat.view
    assert view["verification"]["verified"] is True
    assert view["phase"] == "PROCESS_CASE"
    assert view["selected_case"] == {"case_id": "CL-2048", "case_type": "healthcare", "status": "denied"}
    assert "CL-2048" in reply and "pathology report" in reply
    assert "17 days" in reply  # appeal deadline 2026-03-18 against the demo business date 2026-03-01


def test_nothing_about_claims_is_disclosed_before_verification(chat):
    chat.say("Hi, my name is Margaret Chen and I want to know about my denied healthcare claim from January")
    chat.say("My date of birth is 1985-03-15")
    assert chat.view["verification"]["verified"] is False
    assert chat.view["phase"] == "VERIFY_ID"
    for word in ("CL-2048", "pathology", "$", "denied because"):
        assert word not in chat.transcript.replace("denied healthcare claim", "")
    # The early hint is remembered and used as soon as verification completes.
    reply = chat.say("SSN last four is 4472")
    assert chat.view["selected_case"]["case_id"] == "CL-2048"
    assert "CL-2048" in reply


def test_verification_fields_are_listed_by_name_only(chat):
    chat.say("My name is Margaret Chen and my DOB is 1985-03-15")
    verification = chat.view["verification"]
    assert sorted(verification["fields_provided"]) == ["dob", "full_name"]
    assert "margaret" not in str(chat.view["memory"]).lower()


def test_out_of_scope_is_declined_then_a_human_is_offered_then_requested(chat):
    first = chat.say("What is RL?")
    assert "only help with your insurance claims" in first and "human" not in first
    second = chat.say("What is RL?")
    assert "human representative" in second
    assert chat.view["lifecycle"] == "ACTIVE"
    chat.say("What is RL?")
    assert chat.view["lifecycle"] == "HANDOFF_PENDING"
    assert "simulated" in chat.last_reply


def test_three_failed_verification_attempts_stop_automated_matching(chat):
    for _ in range(2):
        chat.say("My name is Margaret Chen, DOB 1985-03-15, SSN last four 1111")
        assert chat.view["lifecycle"] == "ACTIVE"
        assert "couldn't verify" in chat.last_reply
    chat.say("My name is Margaret Chen, DOB 1985-03-15, SSN last four 2222")
    assert chat.view["lifecycle"] == "HANDOFF_PENDING"
    assert chat.view["verification"]["verified"] is False
    chat.say(MARGARET)
    assert chat.view["verification"]["verified"] is False  # locked: no more automated matching


def test_national_id_holder_verifies_with_another_field_instead_of_ssn(chat, runtime):
    chat.say("My name is Ma Tian, DOB 1964-09-10, SSN last four 6688")
    assert chat.view["verification"]["verified"] is False
    phone = runtime.fixtures.policyholder("P12").phone
    chat.say(f"My name is Ma Tian, DOB 1964-09-10, my phone is {phone}")
    assert chat.view["verification"]["verified"] is True


def test_another_customers_claim_is_indistinguishable_from_a_missing_one(chat):
    chat.say(MARGARET)
    reply = chat.say("What about claim CL-3001?")
    assert "couldn't find a claim" in reply
    assert "2026-04-15" not in chat.transcript
    reply_missing = chat.say("What about claim CL-9999?")
    assert "couldn't find a claim" in reply_missing


def test_choosing_between_two_january_healthcare_claims(chat):
    chat.say("My name is Margaret Chen, DOB 1985-03-15, SSN last four 4472")
    assert chat.view["phase"] == "RESOLVE_INTENT"
    reply = chat.say("It's about my healthcare claim from January")
    assert "CL-2048" in reply and "CL-2011" in reply
    chat.say("The denied one")
    assert chat.view["selected_case"]["case_id"] == "CL-2048"


def test_summary_is_sent_only_after_consent_and_only_once(chat, mailer):
    chat.say(MARGARET)
    chat.say("That's all, thanks")
    assert chat.view["phase"] == "POST_PROCESS"
    assert chat.view["summary"]["status"] == "offered"
    assert chat.view["summary"]["recipient"] == "m*******@email.com"
    assert "send_summary" in chat.view["available_actions"]
    assert mailer.sent == {}
    chat.act("send_summary")
    assert chat.view["summary"]["status"] == "sent"
    assert len(mailer.sent) == 1
    (to, subject, body), = mailer.sent.values()
    assert to == "margaret@email.com" and "CL-2048" in subject and "Appeal deadline: 2026-03-18" in body
    chat.act("send_summary", expect=409)
    assert len(mailer.sent) == 1


def test_a_typed_no_skips_the_summary(chat, mailer):
    chat.say(MARGARET)
    chat.say("that's all")
    chat.say("no thanks")
    assert chat.view["summary"]["status"] == "skipped"
    assert mailer.sent == {}


def test_a_new_question_withdraws_the_summary_preview(chat, mailer):
    chat.say(MARGARET)
    chat.say("that's all")
    chat.say("Actually, how long does processing take after I submit?")
    assert chat.view["phase"] == "PROCESS_CASE"
    assert chat.view["summary"]["status"] == "none"
    assert "less than a week" in chat.last_reply
    chat.say("that's all")
    chat.act("send_summary")
    assert len(mailer.sent) == 1


def test_asking_for_a_human_requests_a_handoff_without_claiming_a_connection(chat):
    reply = chat.say("I want to talk to a human")
    assert chat.view["lifecycle"] == "HANDOFF_PENDING"
    assert "requested" in reply and "connected" not in reply
    chat.say("hello?")
    assert "already been requested" in chat.last_reply


def test_refusing_identity_details_twice_offers_a_human(chat):
    first = chat.say("Why do you need my SSN? I don't want to give it")
    assert "right person" in first and "human" not in first
    second = chat.say("I'm not comfortable giving that")
    assert "human representative" in second


def test_an_ambiguous_date_of_birth_is_clarified_not_guessed(chat):
    reply = chat.say("My name is Margaret Chen, DOB 03/04/1985")
    assert "March 4, 1985" in reply and "April 3, 1985" in reply
    assert chat.view["verification"]["fields_provided"] == ["full_name"]


def test_session_tokens_are_required(client, chat):
    assert client.get(f"/api/sessions/{chat.session_id}").status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert client.get(f"/api/sessions/{chat.session_id}", headers=wrong).status_code == 404
    assert client.get("/api/sessions/unknown", headers=chat.headers).status_code == 404


def test_idle_verification_expires_and_hides_earlier_claim_details(chat, runtime):
    chat.say(MARGARET)
    assert "CL-2048" in chat.transcript
    later = runtime.clock.now() + timedelta(minutes=31)
    runtime.clock = type("Later", (), {"now": lambda self: later, "business_date": runtime.clock.business_date})()
    runtime.engine.clock = runtime.clock
    chat.say("what's next?")
    view = chat.view
    assert view["phase"] == "VERIFY_ID" and view["verification"]["verified"] is False
    assert "CL-2048" not in chat.transcript
    assert "expired" in chat.last_reply


def test_ending_after_a_claim_discussion_offers_the_summary(chat):
    chat.say(MARGARET)
    chat.act("end_conversation")
    assert chat.view["summary"]["status"] == "offered"
    chat.act("skip_summary")
    assert chat.view["lifecycle"] == "CLOSED"
    assert chat.view["available_actions"] == []


def test_health_reports_offline_mode_without_a_key(client):
    assert client.get("/api/health").json()["model_mode"] == "offline"
