"""Test a frozen exclusion candidate independently of development Python imports.

Runs approved self-tests only, with isolated writable data and no developer PATH.
Records DLLs actually mapped in each child process, not just files on disk.
"""

import argparse
import ctypes
import json
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path


def loaded_modules(process: int) -> list[str]:
    """Read only the test child process's loaded image paths using Windows PSAPI."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.EnumProcessModulesEx.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HMODULE),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
    ]
    psapi.GetModuleFileNameExW.argtypes = [
        wintypes.HANDLE,
        wintypes.HMODULE,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    handle = kernel.OpenProcess(0x0400 | 0x0010, False, process)
    if not handle:
        return []
    try:
        modules = (wintypes.HMODULE * 4096)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcessModulesEx(
            handle, modules, ctypes.sizeof(modules), ctypes.byref(needed), 3
        ):
            return []
        paths = []
        for module in modules[: min(len(modules), needed.value // ctypes.sizeof(wintypes.HMODULE))]:
            buffer = ctypes.create_unicode_buffer(32768)
            if psapi.GetModuleFileNameExW(handle, module, buffer, len(buffer)):
                paths.append(buffer.value)
        return paths
    finally:
        kernel.CloseHandle(handle)


def test_candidate(executable: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Use a new test report directory: {output}")
    output.mkdir(parents=True)
    environment = os.environ.copy()
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "NEURALHEAT_PROJECT_ROOT",
        "NEURALHEAT_FRONTEND_DIST",
        "CUDA_PATH",
        "CUDA_PATH_V12_8",
        "NVTOOLSEXT_PATH",
    ):
        environment.pop(name, None)
    environment["PATH"] = os.pathsep.join(
        [str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"]]
    )
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        environment[name] = "http://127.0.0.1:9"
    tests = [
        ("packaged-cpu", ["--device", "cpu"]),
        ("packaged-cuda-worker", ["--device", "cuda", "--verify-worker"]),
        ("packaged-webview-cuda-worker", ["--device", "cuda", "--ui-test", "--verify-worker"]),
    ]
    results = []
    for name, flags in tests:
        user = output / (name + "-userdata")
        user.mkdir()
        report = output / (name + ".json")
        arguments = [
            str(executable),
            "--self-test",
            "--user-data-dir",
            str(user),
            "--test-report",
            str(report),
            *flags,
        ]
        observed, started = set(), time.monotonic()
        with (output / (name + "-process.log")).open("w", encoding="utf-8") as console:
            process = subprocess.Popen(
                arguments,
                cwd=user,
                env=environment,
                stdout=console,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            timed_out = False
            while process.poll() is None:
                observed.update(loaded_modules(process.pid))
                if time.monotonic() - started > 600:
                    process.kill()
                    timed_out = True
                    break
                time.sleep(0.2)
            code = process.wait(timeout=15)
        evidence = (
            json.loads(report.read_text(encoding="utf-8"))
            if report.exists()
            else {"status": "no_report"}
        )
        cuda_images = [
            p
            for p in observed
            if Path(p).name.lower()
            in {"torch_cuda.dll", "cudart64_12.dll", "cudnn64_9.dll", "cusolver64_11.dll"}
        ]
        mg_images = [p for p in observed if "cusolvermg" in Path(p).name.lower()]
        result = {
            "name": name,
            "exit_code": code,
            "timed_out": timed_out,
            "elapsed_seconds": time.monotonic() - started,
            "frozen_report": evidence,
            "observed_modules": sorted(observed),
            "cuda_images": sorted(cuda_images),
            "cusolvermg_images": sorted(mg_images),
            "no_original_or_venv_fallback": not any(
                "site-packages" in p.lower() or "20261021-184035-046" in p.lower() for p in observed
            ),
        }
        result["passed"] = (
            code == 0
            and evidence.get("status") == "passed"
            and evidence.get("frozen") is True
            and evidence.get("backend_port_closed") is True
            and not mg_images
            and result["no_original_or_venv_fallback"]
            and evidence.get("device") == ("cpu" if name == "packaged-cpu" else "cuda")
            and (name == "packaged-cpu" or bool(cuda_images))
        )
        results.append(result)
        (output / "runtime-tests.json").write_text(
            json.dumps(
                {
                    "executable": str(executable),
                    "tests": results,
                    "status": "passed"
                    if len(results) == 3 and all(r["passed"] for r in results)
                    else "incomplete_or_failed",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "test": name,
                    "passed": result["passed"],
                    "exit_code": code,
                    "device": evidence.get("device"),
                    "Mg_loaded": bool(mg_images),
                    "error": evidence.get("error"),
                }
            ),
            flush=True,
        )
    return {"tests": results, "passed": all(r["passed"] for r in results)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = test_candidate(args.executable.resolve(), args.output.resolve())
    raise SystemExit(0 if result["passed"] else 1)
