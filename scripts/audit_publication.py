"""Read-only source/history audit; reports contain locations, never secret values.

Without an existing Git repository, use an ignored temporary Git directory to
apply the real .gitignore rules. Never initialize or stage the project itself.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "openai_style_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "credential_url": re.compile(r"https?://[^\s/:@]+:[^\s/@]{6,}@"),
    "npm_auth": re.compile(r"(?:_authToken|_password)\s*=\s*[A-Za-z0-9_+/=-]{16,}"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "credential_assignment_candidate": re.compile(
        r"(?i)\b(?:api_?key|client_secret|password|passwd|secret_access_key|access_token|auth_token)"
        r"\s*[:=]\s*[\"']([A-Za-z0-9_+/=.!:@#$%-]{20,})[\"']"
    ),
}
PERSONAL_PATH = re.compile(r"(?i)(?:[A-Z]:[\\/]+Users[\\/]+)([^\\/\s\"<>]+)")
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".json",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".ps1",
    ".iss",
    ".css",
    ".html",
    ".svg",
    ".csv",
}


def documentation_checks(root: Path, candidates: set[str]) -> dict:
    """Check public links and captured-UI provenance without running the software."""
    missing, ignored = [], []
    documents = [
        root / "README.md",
        root / "THIRD_PARTY_NOTICES.md",
        *root.glob("docs/*.md"),
        root / "docs/screenshots/README.md",
    ]
    for document in documents:
        if not document.exists():
            missing.append(str(document.relative_to(root)))
            continue
        contents = document.read_text(encoding="utf-8")
        targets = re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", contents)
        targets += re.findall(r"""(?:src|href)=["']([^"']+)["']""", contents)
        for target in targets:
            if ":" in target or target.startswith("#"):
                continue
            destination = (document.parent / target.split("#")[0]).resolve()
            try:
                relative = destination.relative_to(root).as_posix()
            except ValueError:
                missing.append(f"{document.relative_to(root)} -> outside repository")
                continue
            if not destination.exists():
                missing.append(f"{document.relative_to(root)} -> {target}")
            elif destination.is_file() and relative not in candidates:
                ignored.append(f"{document.relative_to(root)} -> {target}")
    screenshot = root / "docs/screenshots/provenance.json"
    capture = json.loads(screenshot.read_text(encoding="utf-8")) if screenshot.exists() else {}
    benchmark = json.loads((root / "reports/benchmark.json").read_text(encoding="utf-8"))
    evaluation = json.loads((root / "reports/evaluation.json").read_text(encoding="utf-8"))
    expected = benchmark["accuracy"]["checkpoint_sha256"]
    images = capture.get("images", [])
    integrity = []
    for row in images:
        path = screenshot.parent / row["image"]
        data = path.read_bytes() if path.is_file() else b""
        integrity.append(
            data.startswith(b"\x89PNG\r\n\x1a\n")
            and len(data) == row["bytes"]
            and hashlib.sha256(data).hexdigest() == row["sha256"]
            and int.from_bytes(data[16:20], "big") == row["width"]
            and int.from_bytes(data[20:24], "big") == row["height"]
        )
    # Manual captures establish visual provenance, not checkpoint/API test results.
    screenshot_checks = {
        "manual_provenance": capture.get("method")
        == "manual Windows captures supplied by the maintainer",
        "review_record": bool(capture.get("reviewed")),
        "available_views": {row["image"] for row in images}
        == {"loading.png", "overview.png", "physics.png", "network.png"},
        "published_image_integrity": bool(integrity) and all(integrity),
        "lossless_compression_verified": bool(images)
        and all(row["pixels_identical"] and row["bytes"] <= row["source_bytes"] for row in images),
    }
    readme = (root / "README.md").read_text(encoding="utf-8")
    evidence = {
        "evaluation_matches_benchmark": evaluation["surrogate"]
        == benchmark["accuracy"]["surrogate"]
        and evaluation["checkpoint_sha256"] == expected,
        "documented_global_l2": f"{benchmark['accuracy']['surrogate']['relative_l2'] * 100:.5f}%"
        in readme,
        "reported_latency_rows": len(benchmark["latency"]) == 15
        and all(
            len(row["raw_times_ms"]) == row["repeats"] == 100 and row["warmup"] == 10
            for row in benchmark["latency"]
        ),
    }
    for row in benchmark["latency"]:
        if row["method"] == "torch_cuda_end_to_end":
            evidence[f"gpu_batch_{row['batch_size']}_median_documented"] = (
                f"{row['median_ms']:.4f}" in readme
            )
    return {
        "missing_links": missing,
        "links_to_ignored_files": ignored,
        "screenshots": screenshot_checks,
        "scientific_evidence": evidence,
    }


def scan_text(data: bytes, location: str) -> list[dict]:
    if b"\0" in data:
        return []
    text = data.decode("utf-8", errors="replace")
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append({"location": location, "line": number, "kind": name})
        for match in PERSONAL_PATH.finditer(line):
            if match.group(1).lower() not in {"public", "default", "username", "user", "example"}:
                findings.append(
                    {"location": location, "line": number, "kind": "personal_windows_path"}
                )
    return findings


def audit(root: Path, output: Path) -> dict:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git is required to verify actual ignore behavior")
    root = root.resolve()
    output.mkdir(parents=True, exist_ok=True)

    def run(arguments: list[str], *, command: list[str] | None = None) -> bytes:
        return subprocess.check_output(
            command or [git, "-C", str(root), *arguments], stderr=subprocess.PIPE
        )

    try:
        repository = Path(run(["rev-parse", "--show-toplevel"]).decode().strip()).resolve()
        existing = repository == root
    except subprocess.CalledProcessError:
        existing = False
    if existing:
        prefix = [git, "-C", str(root), "-c", f"core.excludesFile={os.devnull}"]
    else:
        temporary = output / ("ignore-check-" + uuid4().hex) / "git"
        temporary.parent.mkdir(parents=True)
        prefix = [
            git,
            f"--git-dir={temporary}",
            f"--work-tree={root}",
            "-c",
            f"core.excludesFile={os.devnull}",
        ]
        run([], command=[*prefix, "init", "--quiet", "--initial-branch=main"])

    def git_bytes(*arguments: str) -> bytes:
        return run([], command=[*prefix, *arguments])

    def paths(*arguments: str) -> list[str]:
        names = git_bytes(*arguments, "-z").decode("utf-8").split("\0")
        return sorted(set(names) - {""})

    tracked = paths("ls-files", "--cached")
    ignored_tracked = paths("ls-files", "--cached", "--ignored", "--exclude-standard")
    candidates = sorted(set(tracked) | set(paths("ls-files", "--others", "--exclude-standard")))
    files, findings = [], []
    for name in candidates:
        path = root / name
        if not path.is_file():
            continue
        size = path.stat().st_size
        files.append(
            {
                "path": name,
                "bytes": size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                if size < 50 * 1024**2
                else None,
            }
        )
        if size <= 5 * 1024**2 and (
            path.suffix.lower() in TEXT_SUFFIXES
            or path.name in {"LICENSE", ".gitignore", ".gitattributes"}
        ):
            findings += scan_text(path.read_bytes(), name)
    history = {
        "applicable": existing,
        "commits": 0,
        "blobs_scanned": 0,
        "large_blobs": [],
        "findings": [],
    }
    if existing:
        try:
            history["commits"] = int(git_bytes("rev-list", "--all", "--count").strip() or b"0")
            objects = git_bytes("rev-list", "--objects", "--all", "--reflog").decode().splitlines()
        except subprocess.CalledProcessError:
            objects = []
        for record in objects:
            oid, _, name = record.partition(" ")
            if git_bytes("cat-file", "-t", oid).strip() != b"blob":
                continue
            size = int(git_bytes("cat-file", "-s", oid))
            if size > 5 * 1024**2:
                history["large_blobs"].append({"object": oid, "path": name, "bytes": size})
            else:
                history["findings"] += scan_text(git_bytes("cat-file", "-p", oid), f"{oid}:{name}")
                history["blobs_scanned"] += 1
    probes = [
        ".venv/pyvenv.cfg",
        "dist/release.exe",
        "build/output",
        "node_modules/package.json",
        "frontend/node_modules/package.json",
        "data/sample.npy",
        "runs/experiment/result.json",
        "models/best.pt",
        "NeuralHeat-Studio-Windows.zip",
        "NeuralHeat-Studio-Setup.exe",
        "local.7z",
        ".env",
        "signing.pfx",
        "reports/installer/private.json",
        ".cache/temp.txt",
    ]
    ignore_checks = {}
    for name in probes:
        check = subprocess.run(
            [*prefix, "check-ignore", "--no-index", "--quiet", name], capture_output=True
        )
        ignore_checks[name] = check.returncode == 0
    result = {
        "git_repository_present": existing,
        "project_git_initialized_by_audit": False,
        "tracked_file_count": len(tracked),
        "tracked_but_ignored": ignored_tracked,
        "candidate_file_count": len(files),
        "candidate_bytes": sum(row["bytes"] for row in files),
        "candidate_mib": sum(row["bytes"] for row in files) / 1024**2,
        "largest_files": sorted(files, key=lambda row: row["bytes"], reverse=True)[:15],
        "files_over_5_mib": [row for row in files if row["bytes"] > 5 * 1024**2],
        "credential_findings": [row for row in findings if row["kind"] != "personal_windows_path"],
        "personal_path_findings": [
            row for row in findings if row["kind"] == "personal_windows_path"
        ],
        "history": history,
        "ignore_checks": ignore_checks,
        "files": files,
        "scope": "Prospective source files and tracked history, not ignored local environments or arbitrary binary contents. Pattern scan is not proof that all possible secrets are absent.",
    }
    result["status"] = (
        "passed"
        if not (
            ignored_tracked
            or result["files_over_5_mib"]
            or result["credential_findings"]
            or result["personal_path_findings"]
            or history["findings"]
            or history["large_blobs"]
            or not all(ignore_checks.values())
        )
        else "review_required"
    )
    result["source_checks_status"] = result["status"]
    result["documentation"] = documentation_checks(root, {row["path"] for row in files})
    docs = result["documentation"]
    if (
        docs["missing_links"]
        or docs["links_to_ignored_files"]
        or not all(docs["screenshots"].values())
        or not all(docs["scientific_evidence"].values())
    ):
        result["status"] = "review_required"
    (output / "audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"files", "largest_files", "scope"}
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.root, args.output or args.root / ".cache/publication-audit")
    raise SystemExit(0 if result["status"] == "passed" else 1)
