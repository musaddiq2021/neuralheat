"""Archive the official downloaded Community terms and extract their actual text.

Does not accept terms or infer a distribution grant. A reviewer reads the output
before updating the existing redistribution record.
"""

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

OFFICIAL_URL = (
    "https://visualstudio.microsoft.com/wp-content/uploads/2025/10/"
    "Visual_Studio_2026-License-Community_ENU.docx"
)


def archive(source: Path, destination: Path) -> dict:
    """Retain original bytes, readable paragraphs and a source/hash record."""
    data = source.read_bytes()
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(source) as document:
        body = ElementTree.fromstring(document.read("word/document.xml"))
    paragraphs = [
        "".join(text.text or "" for text in paragraph.findall(".//w:t", namespace))
        for paragraph in body.findall(".//w:p", namespace)
    ]
    text = "\n".join(paragraphs).strip() + "\n"
    upper = text.upper()
    if not all(word in upper for word in ("MICROSOFT", "VISUAL STUDIO", "COMMUNITY", "2026")):
        raise ValueError("Downloaded document is not the expected Community 2026 licence")
    destination.mkdir(parents=True, exist_ok=True)
    stem = "Microsoft-Visual-Studio-Community-2026"
    original = destination / (stem + ".docx")
    readable = destination / (stem + ".txt")
    header = (
        "Official Microsoft Visual Studio Community 2026 licence document\n"
        f"Source: {OFFICIAL_URL}\n"
        f"Original DOCX SHA256: {hashlib.sha256(data).hexdigest()}\n"
        "Readable extraction of Word body paragraphs; original formatting and\n"
        "automatic list numbering are preserved in the accompanying DOCX.\n"
        "The original document controls. No licence is accepted by this script.\n\n"
    )
    if original.exists() and original.read_bytes() != data:
        raise FileExistsError("Existing archived licence differs; review the new version separately")
    original.write_bytes(data)
    readable.write_text(header + text, encoding="utf-8")
    evidence = {
        "source_url": OFFICIAL_URL, "original": original.name,
        "original_sha256": hashlib.sha256(data).hexdigest(), "original_bytes": len(data),
        "readable": readable.name, "readable_sha256": hashlib.sha256(readable.read_bytes()).hexdigest(),
        "publisher_acceptance_previously_confirmed": "2026-10-23", "accepted_by_script": False,
        "full_clause_review_performed_by_script": False,
    }
    (destination / (stem + ".json")).write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=Path("docs/licenses/vendor"))
    options = parser.parse_args()
    print(json.dumps(archive(options.source, options.destination), indent=2))
