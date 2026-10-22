"""Archive verification must detect content changes, omissions and extra files."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_desktop_bundle import audit
from verify_distribution import final_report, verify_tree


def test_bundle_audit_measures_sizes_and_exact_duplicates(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "NeuralHeat Studio.exe").write_bytes(b"executable-fixture")
    (bundle / "copy-a.txt").write_bytes(b"identical contents")
    (bundle / "copy-b.txt").write_bytes(b"identical contents")
    manifest = audit(bundle, tmp_path / "reports")
    assert manifest["file_count"] == 3
    assert manifest["uncompressed_bytes"] == sum(path.stat().st_size for path in bundle.iterdir())
    assert manifest["duplicate_redundant_bytes"] == len(b"identical contents")
    assert verify_tree(bundle, manifest)["status"] == "passed"


def test_extraction_integrity_detects_same_size_corruption(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "NeuralHeat Studio.exe").write_bytes(b"first")
    manifest = audit(bundle, tmp_path / "reports")
    (bundle / "NeuralHeat Studio.exe").write_bytes(b"other")
    result = verify_tree(bundle, manifest)
    assert result["status"] == "failed"
    assert result["changed"] == ["NeuralHeat Studio.exe"]


def test_extraction_integrity_detects_missing_and_unexpected_files(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "NeuralHeat Studio.exe").write_bytes(b"fixture")
    manifest = audit(bundle, tmp_path / "reports")
    (bundle / "NeuralHeat Studio.exe").rename(bundle / "unexpected.bin")
    result = verify_tree(bundle, manifest)
    assert result["status"] == "failed"
    assert result["missing"] == ["NeuralHeat Studio.exe"]
    assert result["unexpected"] == ["unexpected.bin"]


def test_missing_packaged_tests_cannot_be_reported_as_a_verified_release(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "NeuralHeat Studio.exe").write_bytes(b"fixture")
    report_directory = tmp_path / "audit"
    audit(bundle, report_directory)
    archive = tmp_path / "fixture.tar.xz"
    archive.write_bytes(b"archive fixture")
    result = final_report(
        archive,
        bundle,
        report_directory / "bundle-audit.json",
        tmp_path / "missing-tests",
        tmp_path / "result",
    )
    assert result["meets_target"]
    assert result["status"] == "unverified"
    assert all(item["status"] == "not_run" for item in result["packaged_tests"].values())
    assert json.loads((tmp_path / "result/distribution.json").read_text())["status"] == "unverified"
