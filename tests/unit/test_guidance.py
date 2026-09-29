import json
from urllib.parse import unquote

import pytest

from app.claims.guidance import (
    SOURCE,
    GuidanceLibrary,
    GuidanceRenderError,
    UnknownTopic,
    _source,
    natural_list,
    render_template,
)


@pytest.fixture(scope="module")
def library(store, catalog):
    return GuidanceLibrary(store.guideline, catalog)


@pytest.fixture(scope="module")
def raw_guideline(fixtures_dir):
    return json.loads((fixtures_dir / SOURCE).read_text(encoding="utf-8"))


def _resolve(source, document):
    """Follows a snippet's source back into the raw fixture JSON."""
    file, _, fragment = source.partition("#")
    assert file == SOURCE
    node = document
    for token in fragment.removeprefix("/").split("/"):
        token = unquote(token).replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _with_rule(guideline, index, **changes):
    rules = list(guideline.claim_followup_guidance)
    rules[index] = rules[index].model_copy(update=changes)
    return guideline.model_copy(update={"claim_followup_guidance": tuple(rules)})


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


def test_every_snippet_points_at_its_own_text(library, store, catalog, raw_guideline):
    labels = list(catalog.label_to_code)
    snippets = [
        *(s for case_type in store.guideline.case_type_guidance for s in library.for_documents(case_type, labels)),
        *(library.alternatives(label) for label in labels),
        library.human_review_rule(),
        library.fallback(),
    ]
    for snippet in snippets:
        assert _resolve(snippet.source, raw_guideline) == snippet.text, snippet.topic


def test_every_followup_points_at_its_own_template(library, store, raw_guideline):
    claim = store.claim("CL-2048")
    settings = raw_guideline["claim_followup_settings"]
    values = {
        "case_id": claim.case_id,
        "documents": natural_list(claim.documents_needed),
        "average_processing_time_after_submission": settings["average_processing_time_after_submission"]["en"],
    }
    for topic in library.topics:
        snippet = library.followup(claim, topic)
        assert _resolve(snippet.source.removesuffix("/en"), raw_guideline)["topic"] == topic
        assert render_template(_resolve(snippet.source, raw_guideline), values) == snippet.text


def test_source_escapes_tilde_and_slash_before_percent_encoding():
    assert _source("a/b~c", "en") == f"{SOURCE}#/a~1b~0c/en"
    assert _source("~1") == f"{SOURCE}#/~01"
    assert _source("x ray", 3) == f"{SOURCE}#/x%20ray/3"


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


def test_a_document_named_twice_is_requested_once(library, store):
    claim = store.claim("CL-2048").model_copy(
        update={"documents_needed": ("pathology report", "original pathology report", "office note")}
    )
    text = library.followup(claim, "submission_timing").text
    assert text == "For claim CL-2048, please submit pathology report and office note within a week."


def test_templates_do_not_apply_to_a_claim_without_documents(library, store):
    snippet = library.followup(store.claim("CL-2102"), "submission_method")
    assert snippet == library.fallback()
    assert snippet.source.endswith("#/claim_followup_fallback/en")


def test_a_rule_that_does_not_need_documents_renders_without_them(store, catalog):
    library = GuidanceLibrary(_with_rule(store.guideline, 0, requires_documents=False), catalog)
    text = library.followup(store.claim("CL-2102"), "missing_required_material_alternatives").text
    assert text.startswith("For claim CL-2102, if the exact requested item is not available")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"en": "For claim {case_Id}, submit {documents}."}, r"submission_timing\): unknown placeholder \{case_Id\}"),
        ({"en": "For claim {case_id, submit {documents}."}, r"submission_timing\): template has an unmatched brace"),
        ({"requires_documents": False}, r"submission_timing\): uses \{documents\} but does not require documents"),
    ],
    ids=["unknown-placeholder", "unmatched-brace", "documents-not-required"],
)
def test_templates_are_checked_when_the_library_is_built(store, catalog, changes, message):
    with pytest.raises(GuidanceRenderError, match=message):
        GuidanceLibrary(_with_rule(store.guideline, 1, **changes), catalog)


def test_a_repeated_topic_is_rejected(store, catalog):
    rules = store.guideline.claim_followup_guidance
    guideline = store.guideline.model_copy(update={"claim_followup_guidance": (*rules, rules[0])})
    with pytest.raises(ValueError, match="topic 'missing_required_material_alternatives' repeats"):
        GuidanceLibrary(guideline, catalog)


def test_guidance_keys_that_share_a_document_code_are_rejected(store, catalog):
    guidance = dict(store.guideline.document_guidance)
    guidance["pathology report"] = guidance["original pathology report"]
    guideline = store.guideline.model_copy(update={"document_guidance": guidance})
    with pytest.raises(ValueError, match="share document code PATHOLOGY_REPORT"):
        GuidanceLibrary(guideline, catalog)


def test_unknown_topic_is_rejected(library, store):
    with pytest.raises(UnknownTopic):
        library.followup(store.claim("CL-2048"), "refund_status")
    with pytest.raises(UnknownTopic):
        library.topic_examples("refund_status")


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
        ("Submit documents} soon.", {"documents": "a pathology report"}, "unmatched brace"),
    ],
    ids=[
        "empty-value",
        "blank-value",
        "missing-value",
        "unknown-placeholder",
        "unmatched-open-brace",
        "unmatched-close-brace",
    ],
)
def test_rendering_refuses_a_template_it_cannot_fill_completely(template, values, message):
    with pytest.raises(GuidanceRenderError, match=message):
        render_template(template, values)


def test_natural_list():
    assert natural_list([]) == ""
    assert natural_list(["a"]) == "a"
    assert natural_list(["a", "b"]) == "a and b"
    assert natural_list(["a", "b", "c"]) == "a, b, and c"
