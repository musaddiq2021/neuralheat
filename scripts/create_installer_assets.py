"""Generate reproducible installer artwork from the existing application identity."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_assets(destination: Path, icon: Path, includes_webview: bool = False) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (328, 628), "#111315")
    draw = ImageDraw.Draw(image)
    for x in range(0, image.width, 32):
        draw.line((x, 0, x, image.height), fill="#1a1e21")
    for y in range(0, image.height, 32):
        draw.line((0, y, image.width, y), fill="#1a1e21")

    def font(size: int, bold: bool = False):
        name = "segoeuib.ttf" if bold else "segoeui.ttf"
        path = Path("C:/Windows/Fonts") / name
        return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()

    mark = Image.open(icon).convert("RGBA").resize((92, 92), Image.Resampling.LANCZOS)
    image.paste(mark, (30, 46), mark)
    draw.text((30, 173), "NEURALHEAT", font=font(33, True), fill="#edf0f2")
    draw.text((30, 216), "STUDIO", font=font(29), fill="#b5c1ca")
    draw.line((32, 282, 292, 282), fill="#45525c", width=2)
    draw.text((32, 312), "SCIENTIFIC COMPUTING", font=font(17), fill="#b5c1ca")
    draw.text((32, 344), "Physics. Inference. Evidence.", font=font(17), fill="#8e9ca6")
    draw.text((32, 525), "LOCAL WORKSTATION", font=font(16), fill="#b5c1ca")
    draw.text((32, 554), "CPU + CUDA", font=font(16), fill="#8e9ca6")
    image.save(destination / "wizard.bmp")
    small = Image.new("RGB", (110, 110), "#111315")
    small.paste(mark, (9, 9), mark)
    small.save(destination / "wizard-small.bmp")
    runtime = (
        "The Microsoft WebView2 offline runtime installer is included and runs only if needed."
        if includes_webview
        else "Microsoft Edge WebView2 Runtime must already be installed. On offline machines, "
        "use Microsoft's Evergreen Standalone Installer (x64) before running Setup."
    )
    (destination / "installation-notes.txt").write_text(
        "NEURALHEAT STUDIO\nScientific computing workstation\n\n"
        "This installer includes the complete application: the heat solver, trained CNN "
        "checkpoint, production interface, saved scientific evidence, matching datasets, "
        "and PyTorch CPU/CUDA dependencies.\n\n"
        "SYSTEM REQUIREMENTS\nWindows 10 (1809 or later) / Windows 11, x64.\n"
        "Allow approximately 4.2 GiB for the application and additional space for experiments.\n"
        "A compatible NVIDIA GPU driver enables CUDA; CPU operation is also supported. "
        "The CUDA Toolkit, Python, and Node.js are not required.\n\n" + runtime + "\n\nYOUR DATA\n"
        "Experiments, logs, caches, and settings are stored separately under "
        "%LOCALAPPDATA%\\NeuralHeat Studio. Uninstalling preserves that personal data. "
        "The supplied checkpoint and historical scientific results are never replaced "
        "by training.\n\n"
        "Setup makes no internet downloads. All application features run locally.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--icon", type=Path, required=True)
    parser.add_argument("--includes-webview", action="store_true")
    args = parser.parse_args()
    create_assets(args.destination, args.icon, args.includes_webview)
