import pytest

from app.claims.documents import UnknownDocumentLabel, load_document_catalog


def test_claim_and_guidance_labels_share_one_code(catalog):
    assert catalog.code_for("pathology report") == "PATHOLOGY_REPORT"
    assert catalog.code_for("original pathology report") == "PATHOLOGY_REPORT"
    assert catalog.code_for("office note") == "PROVIDER_OFFICE_NOTE"
    assert catalog.code_for("treating provider office note") == "PROVIDER_OFFICE_NOTE"
    assert catalog.code_for("diagnosis report") == "DIAGNOSIS_REPORT"


def test_labels_ignore_case_and_extra_spaces(catalog):
    assert catalog.code_for("  Pathology   REPORT ") == "PATHOLOGY_REPORT"


def test_unknown_label_fails_closed(catalog):
    with pytest.raises(UnknownDocumentLabel):
        catalog.code_for("x-ray")


def test_a_label_cannot_map_to_two_codes(tmp_path):
    path = tmp_path / "codes.toml"
    path.write_text('version = "t"\n[codes.A]\nlabels = ["note"]\n[codes.B]\nlabels = ["Note"]\n')
    with pytest.raises(ValueError, match="maps to both"):
        load_document_catalog(path)
