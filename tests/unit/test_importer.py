import hashlib

import pytest

from app.claims.importer import FixtureError, load_fixtures


def _hashes(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob("*.json")}


def test_store_holds_every_fixture_record(store):
    assert len(store.policyholders) == 4
    assert len(store.claims) == 5
    assert len(store.representatives) == 1
    assert set(store.consent_scenarios) == {"default", "timeout"}


def test_claims_are_indexed_by_owner(store):
    assert [c.case_id for c in store.claims_for_party("P9")] == ["CL-2048", "CL-2011", "CL-1899", "CL-2102"]
    assert [c.case_id for c in store.claims_for_party("P12")] == ["CL-3001"]
    assert store.claims_for_party("P7") == ()
    assert store.claims_for_party("P13") == ()


def test_lookups_return_none_for_unknown_ids(store):
    assert store.claim("CL-9999") is None
    assert store.policyholder("P99") is None


def test_store_mappings_are_read_only(store):
    with pytest.raises(TypeError):
        store.claim_versions["CL-2048"] = "tampered"
    with pytest.raises(TypeError):
        store.consent_scenarios["surprise"] = store.consent_scenarios["default"]


def test_claim_versions_are_stable_content_hashes(store, fixtures_dir, catalog):
    assert load_fixtures(fixtures_dir, catalog).claim_versions == store.claim_versions
    assert len(set(store.claim_versions.values())) == 5


def test_a_changed_claim_gets_a_new_version(store, fixture_copy, catalog):
    fixture_copy.edit("claims.json", lambda claims: claims[0].update(status="open"))
    changed = load_fixtures(fixture_copy.path, catalog).claim_versions
    assert changed["CL-2048"] != store.claim_versions["CL-2048"]
    assert changed["CL-2011"] == store.claim_versions["CL-2011"]


def test_loading_leaves_fixture_files_untouched(fixtures_dir, catalog):
    before = _hashes(fixtures_dir)
    load_fixtures(fixtures_dir, catalog)
    assert _hashes(fixtures_dir) == before


def test_claim_owned_by_an_unknown_party_is_rejected(fixture_copy, catalog):
    fixture_copy.edit("claims.json", lambda claims: claims[0].update(party_id="P99"))
    with pytest.raises(FixtureError, match="unknown party P99"):
        load_fixtures(fixture_copy.path, catalog)


def test_representative_must_name_their_policyholder(fixture_copy, catalog):
    fixture_copy.edit("representatives.json", lambda reps: reps[0].update(buyer_name="Someone Else"))
    with pytest.raises(FixtureError, match="does not match a policyholder"):
        load_fixtures(fixture_copy.path, catalog)


def test_document_label_without_a_code_is_rejected(fixture_copy, catalog):
    fixture_copy.edit("claims.json", lambda claims: claims[0].update(documents_needed=["x-ray"]))
    with pytest.raises(FixtureError, match="'x-ray' has no document code"):
        load_fixtures(fixture_copy.path, catalog)


def test_invalid_file_is_named_in_the_error(fixture_copy, catalog):
    fixture_copy.edit(
        "consent_scenarios.json", lambda scenarios: scenarios.update(surprise={"status_sequence": ["maybe"]})
    )
    with pytest.raises(FixtureError, match="consent_scenarios.json"):
        load_fixtures(fixture_copy.path, catalog)


def test_duplicate_case_ids_are_rejected(fixture_copy, catalog):
    fixture_copy.edit("claims.json", lambda claims: claims.append(dict(claims[0])))
    with pytest.raises(FixtureError, match="duplicate case_id: CL-2048"):
        load_fixtures(fixture_copy.path, catalog)


def test_duplicate_followup_topics_are_rejected(fixture_copy, catalog):
    def duplicate_topic(guideline):
        rules = guideline["claim_followup_guidance"]
        rules[1]["topic"] = rules[0]["topic"]

    fixture_copy.edit("required_document_guideline.json", duplicate_topic)
    with pytest.raises(FixtureError, match="duplicate follow-up topic: missing_required_material_alternatives"):
        load_fixtures(fixture_copy.path, catalog)


def test_validation_errors_do_not_echo_record_values(fixture_copy, catalog):
    fixture_copy.edit("policyholders.json", lambda holders: holders[0].update(id_last4="44720"))
    with pytest.raises(FixtureError) as caught:
        load_fixtures(fixture_copy.path, catalog)
    message = str(caught.value)
    assert "policyholders.json" in message and "id_last4" in message
    assert "44720" not in message
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_reference_errors_do_not_echo_names(fixture_copy, catalog):
    fixture_copy.edit("representatives.json", lambda reps: reps[0].update(buyer_party_id="P99"))
    with pytest.raises(FixtureError, match=r"\[0\] buyer does not match a policyholder \(P99\)") as caught:
        load_fixtures(fixture_copy.path, catalog)
    assert "Chen" not in str(caught.value)


def test_duplicate_policy_numbers_name_the_parties_not_the_number(fixture_copy, catalog):
    fixture_copy.edit("policyholders.json", lambda holders: holders[1].update(policy_number="POL-9921"))
    with pytest.raises(FixtureError, match="parties share a policy number: P7, P9") as caught:
        load_fixtures(fixture_copy.path, catalog)
    assert "POL-" not in str(caught.value)


def _drop_default_alternative(guideline):
    del guideline["document_alternative_guidance"]["default"]


def _add_unmapped_guidance_key(guideline):
    guideline["document_guidance"]["x-ray"] = {"en": "text"}


def _add_unmapped_alternative_key(guideline):
    guideline["document_alternative_guidance"]["x-ray"] = {"en": "text"}


def _add_second_key_for_one_document(guideline):
    guideline["document_guidance"]["pathology report"] = {"en": "text"}


def _duplicate_party_id(holders):
    holders[1]["party_id"] = holders[0]["party_id"]


@pytest.mark.parametrize(
    ("name", "change", "message"),
    [
        ("required_document_guideline.json", _drop_default_alternative, "has no default"),
        (
            "required_document_guideline.json",
            _add_unmapped_guidance_key,
            "document_guidance: document label 'x-ray' has no document code",
        ),
        (
            "required_document_guideline.json",
            _add_unmapped_alternative_key,
            "document_alternative_guidance: document label 'x-ray' has no document code",
        ),
        (
            "required_document_guideline.json",
            _add_second_key_for_one_document,
            "document_guidance: 'original pathology report' and 'pathology report' share document code PATHOLOGY_REPORT",
        ),
        ("policyholders.json", _duplicate_party_id, "duplicate party_id: P9"),
    ],
    ids=[
        "missing-default-alternative",
        "unmapped-guidance-key",
        "unmapped-alternative-key",
        "two-keys-for-one-document",
        "duplicate-party-id",
    ],
)
def test_other_reference_errors_are_rejected(fixture_copy, catalog, name, change, message):
    fixture_copy.edit(name, change)
    with pytest.raises(FixtureError, match=message):
        load_fixtures(fixture_copy.path, catalog)


def test_repeated_keys_in_a_json_object_are_rejected(fixture_copy, catalog):
    path = fixture_copy.path / "claims.json"
    text = path.read_text(encoding="utf-8")
    assert '"status": "denied",' in text
    repeated = text.replace('"status": "denied",', '"status": "denied", "status": "open",', 1)
    path.write_text(repeated, encoding="utf-8")
    with pytest.raises(FixtureError, match="claims.json: repeated key in one JSON object: status"):
        load_fixtures(fixture_copy.path, catalog)


@pytest.mark.parametrize(
    "content",
    [b"{not json", '[{"rep_name": "L\u00f3pez"}]'.encode("latin-1"), None],
    ids=["malformed-json", "not-utf8", "missing-file"],
)
def test_unreadable_files_are_named_without_chaining(fixture_copy, catalog, content):
    path = fixture_copy.path / "representatives.json"
    if content is None:
        path.unlink()
    else:
        path.write_bytes(content)
    with pytest.raises(FixtureError, match="representatives.json") as caught:
        load_fixtures(fixture_copy.path, catalog)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
