"""The supplied fixtures are read-only inputs. These are the SHA-256 hashes of the
files as delivered; a mismatch means a fixture was edited instead of the policy overlay."""

import hashlib

DELIVERED_SHA256 = {
    "claim_schema.json": "f95f0b49b4522e56b4b65dbdf4d74204b348bf43a333920a07d8d6589969ec4a",
    "claims.json": "16466e43f33eb7fb4f8aa0a3120f5e636ff38e337fc2673ee5aacdd9deaad76f",
    "consent_scenarios.json": "e1c49b14f21d7f956042f0737a4f5b9c2b09f63e5b4abfbe203df089cd678304",
    "policyholders.json": "7eb92602a256cabe628ddbe31d739609ebf00d9672e327f73ff31ae9bee1189c",
    "representatives.json": "ebc55c04c068a762e3596048fef0ebfeef21b19f595b64e0bdd64cc2c26c8b34",
    "required_document_guideline.json": "bc5425b0970c6e4c4c64b262f1c3c0020287e3e9adc437034c2f96fa6ff36c4b",
}


def test_fixture_files_are_unchanged(fixtures_dir):
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(fixtures_dir.glob("*.json"))
    }
    assert actual == DELIVERED_SHA256
