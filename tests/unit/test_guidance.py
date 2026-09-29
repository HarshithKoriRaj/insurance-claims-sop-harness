import pytest

from app.claims.guidance import (
    GuidanceLibrary,
    GuidanceRenderError,
    UnknownTopic,
    natural_list,
    render_template,
)


@pytest.fixture(scope="module")
def library(store, catalog):
    return GuidanceLibrary(store.guideline, catalog)


def test_denied_claim_gets_general_case_type_and_document_guidance(library, store):
    claim = store.claim("CL-2048")
    topics = [s.topic for s in library.for_documents(claim.case_type, claim.documents_needed)]
    assert topics == ["default", "case_type:healthcare", "document:PATHOLOGY_REPORT", "document:PROVIDER_OFFICE_NOTE"]


def test_diagnosis_report_has_no_specific_guidance(library, store):
    claim = store.claim("CL-3001")
    topics = [s.topic for s in library.for_documents(claim.case_type, claim.documents_needed)]
    assert topics == ["default", "case_type:healthcare"]


def test_alternatives_are_document_specific_or_default(library):
    assert library.alternatives("pathology report").topic == "alternative:PATHOLOGY_REPORT"
    assert library.alternatives("office note").topic == "alternative:PROVIDER_OFFICE_NOTE"
    assert library.alternatives("diagnosis report").topic == "alternative:default"


def test_submission_timing_is_filled_from_the_claim(library, store):
    snippet = library.followup(store.claim("CL-2048"), "submission_timing")
    assert snippet.text == "For claim CL-2048, please submit pathology report and office note within a week."
    assert snippet.source.endswith("#/claim_followup_guidance/1/en")


def test_every_topic_renders_completely_for_a_claim_with_documents(library, store):
    claim = store.claim("CL-2048")
    for topic in library.topics:
        text = library.followup(claim, topic).text
        assert "{" not in text and "}" not in text
        assert "original" not in text


def test_processing_time_comes_from_the_settings(library, store):
    text = library.followup(store.claim("CL-2048"), "processing_time_after_submission").text
    assert "The average processing time is usually less than a week" in text


def test_templates_do_not_apply_to_a_claim_without_documents(library, store):
    assert library.followup(store.claim("CL-2102"), "submission_method") == library.fallback()


def test_unknown_topic_is_rejected(library, store):
    with pytest.raises(UnknownTopic):
        library.followup(store.claim("CL-2048"), "refund_status")


def test_match_any_phrases_are_exposed_only_as_examples(library):
    assert "how long" in library.topic_examples("processing_time_after_submission")
    assert library.topic_examples("missing_required_material_alternatives") == ()


def test_human_review_rule_comes_with_provenance(library):
    rule = library.human_review_rule()
    assert rule.text.startswith("If the caller still cannot provide the requested item")
    assert rule.source.endswith("#/claim_followup_settings/human_review_after_document_alternatives_exhausted/en")


def test_labels_for_the_same_document_give_one_snippet(library):
    snippets = library.for_documents("healthcare", ["pathology report", "original pathology report"])
    assert [s.topic for s in snippets] == ["default", "case_type:healthcare", "document:PATHOLOGY_REPORT"]


def test_sources_are_json_pointers_in_uri_fragment_form(library):
    assert library.alternatives("pathology report").source == (
        "required_document_guideline.json#/document_alternative_guidance/original%20pathology%20report/en"
    )


@pytest.mark.parametrize(
    ("template", "values", "message"),
    [
        ("Submit {documents} soon.", {"documents": ""}, r"no value for placeholder \{documents\}"),
        ("Submit {documents} soon.", {"documents": "   "}, r"no value for placeholder \{documents\}"),
        ("Submit {documents} soon.", {}, r"no value for placeholder \{documents\}"),
        ("Submit {Documents} soon.", {"documents": "a pathology report"}, r"no value for placeholder \{Documents\}"),
        ("Submit {documents soon.", {"documents": "a pathology report"}, "unmatched brace"),
    ],
    ids=["empty-value", "blank-value", "missing-value", "unknown-placeholder", "unmatched-brace"],
)
def test_rendering_refuses_a_template_it_cannot_fill_completely(template, values, message):
    with pytest.raises(GuidanceRenderError, match=message):
        render_template(template, values)


def test_natural_list():
    assert natural_list([]) == ""
    assert natural_list(["a"]) == "a"
    assert natural_list(["a", "b"]) == "a and b"
    assert natural_list(["a", "b", "c"]) == "a, b, and c"
