import pytest
from pydantic import ValidationError

from app.claims.documents import UnknownDocumentLabel, load_document_catalog


@pytest.mark.parametrize(
    ("label", "code"),
    [
        ("pathology report", "PATHOLOGY_REPORT"),
        ("original pathology report", "PATHOLOGY_REPORT"),
        ("office note", "PROVIDER_OFFICE_NOTE"),
        ("treating provider office note", "PROVIDER_OFFICE_NOTE"),
        ("diagnosis report", "DIAGNOSIS_REPORT"),
        ("repair estimate", "REPAIR_ESTIMATE"),
        ("supplemental accident scene photos", "ACCIDENT_SCENE_PHOTOS"),
    ],
)
def test_every_fixture_label_maps_to_its_code(catalog, label, code):
    assert catalog.code_for(label) == code


def test_catalog_version(catalog):
    assert catalog.version == "2026-09-28"


def test_labels_ignore_case_and_extra_spaces(catalog):
    assert catalog.code_for("  Pathology   REPORT ") == "PATHOLOGY_REPORT"


@pytest.mark.parametrize("label", ["x-ray", "   ", ""])
def test_unknown_or_blank_label_fails_closed(catalog, label):
    with pytest.raises(UnknownDocumentLabel):
        catalog.code_for(label)


def test_the_mapping_is_read_only(catalog):
    with pytest.raises(TypeError):
        catalog.label_to_code["x-ray"] = "PATHOLOGY_REPORT"


def test_a_label_cannot_map_to_two_codes(tmp_path):
    path = tmp_path / "codes.toml"
    path.write_text('version = "t"\n[codes.A]\nlabels = ["note"]\n[codes.B]\nlabels = ["Note"]\n')
    with pytest.raises(ValueError, match="maps to both"):
        load_document_catalog(path)


@pytest.mark.parametrize(
    "text",
    [
        '[codes.A]\nlabels = ["note"]\n',
        'version = ""\n[codes.A]\nlabels = ["note"]\n',
        'version = 2026-09-28\n[codes.A]\nlabels = ["note"]\n',
        'version = "t"\n',
        'version = "t"\ncodes = 1\n',
        'version = "t"\n[codes.A]\n',
        'version = "t"\n[codes.A]\nlabels = []\n',
        'version = "t"\n[codes.A]\nlabels = ["   "]\n',
        'version = "t"\n[codes.A]\nlabels = "note"\n',
        'version = "t"\n[codes.A]\nlabels = [1]\n',
        'version = "t"\n[codes."pathology report"]\nlabels = ["note"]\n',
        'version = "t"\n[codes.A]\nlabels = ["note"]\nsurprise = 1\n',
        'version = "t"\nsurprise = 1\n[codes.A]\nlabels = ["note"]\n',
    ],
    ids=[
        "missing-version",
        "empty-version",
        "date-version",
        "missing-codes",
        "codes-not-a-table",
        "missing-labels",
        "no-labels",
        "blank-label",
        "labels-not-a-list",
        "label-not-a-string",
        "code-not-an-identifier",
        "unknown-entry-key",
        "unknown-top-level-key",
    ],
)
def test_malformed_catalog_files_are_rejected(tmp_path, text):
    path = tmp_path / "codes.toml"
    path.write_text(text)
    with pytest.raises(ValidationError):
        load_document_catalog(path)
