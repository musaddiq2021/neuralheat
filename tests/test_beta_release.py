"""Release tooling must not stage unverified or retained-Mg application payloads."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import inspect_msvc_runtime
import prepare_beta_release


def release_fixture(tmp_path, monkeypatch):
    """Synthetic files test gating only; they are not application verification."""
    review = tmp_path / "docs/licenses/redistribution-review.json"
    review.parent.mkdir(parents=True)
    review.write_text(json.dumps({"outstanding": [], "binary_publication_ready": True}))
    (tmp_path / "docs/RELEASE_NOTES.md").write_text("Synthetic release-note fixture.\n")
    checkpoint = tmp_path / "models/best.pt"
    checkpoint.parent.mkdir()
    checkpoint.write_bytes(b"synthetic checkpoint fixture")
    monkeypatch.setattr(prepare_beta_release, "CHECKPOINT",
                        hashlib.sha256(checkpoint.read_bytes()).hexdigest())
    source = tmp_path / "source"
    source.mkdir()
    installer = tmp_path / "build/NeuralHeat-Studio-Setup.exe"
    installer.parent.mkdir()
    installer.write_bytes(b"synthetic installer fixture")
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({
        "source_executable": str(source / "NeuralHeat Studio.exe"),
        "installer": str(installer),
        "installer_sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
    }))
    return source, installer, candidate


def test_retained_mg_cannot_become_upload_ready(tmp_path, monkeypatch):
    source, installer, candidate = release_fixture(tmp_path, monkeypatch)
    mg = source / "_internal/torch/lib/cusolverMg64_11.dll"
    mg.parent.mkdir(parents=True)
    mg.write_bytes(b"retained-component fixture")
    (installer.parent / "installer.json").write_text(json.dumps({"status": "verified"}))
    output = tmp_path / "release"
    result = prepare_beta_release.prepare(tmp_path, candidate, output)
    assert result["status"] == "draft_awaiting_evidence"
    assert any("retains cuSOLVERMg" in reason for reason in result["remaining"])
    assert result["upload_ready_installer"] is None
    assert not (output / installer.name).exists()


def test_missing_installation_evidence_cannot_stage_installer(tmp_path, monkeypatch):
    _, installer, candidate = release_fixture(tmp_path, monkeypatch)
    output = tmp_path / "release"
    result = prepare_beta_release.prepare(tmp_path, candidate, output)
    assert any("installation verification" in reason for reason in result["remaining"])
    assert result["assets"] == []
    assert not (output / installer.name).exists()


def test_runtime_inspector_refuses_unpinned_input_before_extraction(tmp_path):
    installer = tmp_path / "untrusted.exe"
    installer.write_bytes(b"not the official Microsoft package")
    output = tmp_path / "extracted"
    with pytest.raises(ValueError, match="Microsoft's pinned manifest"):
        inspect_msvc_runtime.inspect(installer, output)
    assert not output.exists()


def test_verified_release_stages_hash_bound_assets_and_draft_only(tmp_path, monkeypatch):
    _, installer, candidate = release_fixture(tmp_path, monkeypatch)
    recorded_hash = hashlib.sha256(installer.read_bytes()).hexdigest()
    (installer.parent / "installer.json").write_text(json.dumps({
        "status": "verified", "installer_sha256": recorded_hash,
    }))
    support = tmp_path / "dist/release-support"
    support.mkdir(parents=True)
    for name in ("NeuralHeat-Studio-Third-Party-Notices.txt",
                 "NeuralHeat-Studio-Certifi-2026.4.22-Source.zip"):
        (support / name).write_bytes(b"synthetic accompanying asset fixture")
    output = tmp_path / "release"
    result = prepare_beta_release.prepare(tmp_path, candidate, output)
    assert result["status"] == "ready_for_upload"
    assert result["published"] is False
    assert result["remote_draft_created"] is False
    assert len(result["assets"]) == 4
    assert (output / installer.name).read_bytes() == installer.read_bytes()
    assert recorded_hash in (output / "SHA256SUMS.txt").read_text()
    assert "--draft --prerelease" in (output / "CREATE_GITHUB_DRAFT.ps1").read_text()
