"""Publication scans report locations without exposing matching credential values."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_publication import scan_text


def test_token_detection_reports_location_without_secret_value():
    token = "gh" + "p_" + "A" * 36
    result = scan_text(("first line\n" + token).encode(), "fixture.txt")
    assert result == [{"location": "fixture.txt", "line": 2, "kind": "github_token"}]
    assert token not in str(result)


def test_personal_paths_are_detected_in_plain_and_json_escaped_text():
    raw = "C:" + "\\" + "Users" + "\\" + "Maintainer" + r"\file"
    for value in (raw, raw.replace("\\", "\\\\")):
        assert scan_text(value.encode(), "fixture.txt")[0]["kind"] == "personal_windows_path"
    assert not scan_text(rb"C:\Users\Public\Desktop", "fixture.txt")


def test_binary_data_and_benign_configuration_are_not_secret_findings():
    assert not scan_text(b"\x00binary payload", "fixture.bin")
    assert not scan_text(b"device = 'cuda'\nlearning_rate = 0.001", "fixture.py")
