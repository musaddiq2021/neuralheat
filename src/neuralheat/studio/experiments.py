"""One-at-a-time, allowlisted project experiments with durable SSE log events."""

import asyncio
import copy
import ctypes
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from neuralheat.common import write_json

TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
EPOCH = re.compile(r"epoch (\d+): train ([\d.eE+\-]+) validation ([\d.eE+\-]+)")


class WindowsJob:
    """Own the runner and descendants; closing the handle ends the entire job."""

    def __init__(self, process: subprocess.Popen):
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD),
                ("min_working", ctypes.c_size_t),
                ("max_working", ctypes.c_size_t),
                ("active_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "read_ops",
                    "write_ops",
                    "other_ops",
                    "read_bytes",
                    "write_bytes",
                    "other_bytes",
                )
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Basic),
                ("io", IO),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)
        ) or not kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class ExperimentManager:
    def __init__(self, root: Path, *, work_root: Path | None = None):
        self.root = root.resolve()
        self.work_root = (work_root or root).resolve()
        self.directory = self.work_root / "runs/studio"
        self.lock = threading.RLock()
        self.records: dict[str, dict] = {}
        self.events: dict[str, list[dict]] = {}
        self.process: subprocess.Popen | None = None
        self.job: WindowsJob | None = None
        self.active: str | None = None
        if self.directory.exists():
            for path in self.directory.glob("*/studio.json"):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    if record["status"] not in TERMINAL:
                        record["status"] = "interrupted"
                        write_json(path, record)
                    self.records[record["id"]] = record
                except (OSError, ValueError, KeyError):
                    continue

    def _save(self, identifier: str) -> None:
        write_json(self.directory / identifier / "studio.json", self.records[identifier])

    def _event(self, identifier: str, kind: str, data: dict) -> None:
        events = self.events.setdefault(identifier, [])
        sequence = events[-1]["id"] + 1 if events else 1
        event = {"id": sequence, "event": kind, "data": copy.deepcopy(data)}
        events.append(event)
        if len(events) > 10000:
            del events[:1000]
        with (self.directory / identifier / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")

    def start(self, preset: str) -> dict:
        if preset not in {"smoke", "full"}:
            raise ValueError("Only smoke and full project presets are permitted")
        with self.lock:
            if self.active is not None:
                raise ValueError(
                    "An experiment is already running; cancel it before starting another"
                )
            preset_config = json.loads(
                (self.root / f"configs/{preset}.json").read_text(encoding="utf-8")
            )
            identifier = (
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
            )
            output = self.directory / identifier
            output.mkdir(parents=True)
            command = [
                sys.executable,
                "-u",
                str(self.root / "scripts/run_experiment.py"),
                "--config",
                str(self.root / f"configs/{preset}.json"),
                "--output-root",
                str(output),
            ]
            frozen = getattr(sys, "frozen", False)
            if frozen:
                # A frozen executable is not a Python interpreter. Dispatch a
                # fixed worker mode inside the same distributable instead.
                command = [
                    sys.executable,
                    "--experiment-worker",
                    preset,
                    "--user-data-dir",
                    str(self.work_root),
                    "--output-root",
                    str(output),
                ]
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONPATH"] = str(self.root / "src") + os.pathsep + env.get("PYTHONPATH", "")
            # Every argv component is server-owned; no shell, user flags or paths.
            process = subprocess.Popen(
                command,
                cwd=self.work_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0,
                start_new_session=os.name != "nt",
            )
            try:
                self.job = WindowsJob(process) if os.name == "nt" else None
            except OSError:
                process.kill()
                process.wait()
                raise
            self.process, self.active = process, identifier
            self.records[identifier] = {
                "id": identifier,
                "preset": preset,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": None,
                "return_code": None,
                "epoch": 0,
                "epoch_limit": preset_config["training"]["epochs"],
                "history": [],
                "relative_path": str(output.relative_to(self.work_root)),
                "command": command,
            }
            self._save(identifier)
            self._event(identifier, "state", self.records[identifier].copy())
            threading.Thread(
                target=self._read,
                args=(identifier, process, output / "worker.log" if frozen else None),
                daemon=True,
            ).start()
            return self.records[identifier].copy()

    @staticmethod
    def _worker_lines(path: Path, process: subprocess.Popen):
        # Windowed PyInstaller sets sys.stdout=None. Workers log to a file
        # instead of depending on inherited console/CRT handles.
        while not path.exists():
            if process.poll() is not None:
                yield "Worker exited before writing its log; inspect desktop logs.\n"
                return
            time.sleep(0.1)
        with path.open(encoding="utf-8", errors="replace") as handle:
            pending = ""
            while True:
                chunk = handle.read()
                pending += chunk
                while "\n" in pending:
                    line, pending = pending.split("\n", 1)
                    yield line + "\n"
                if process.poll() is not None:
                    # One final read drains bytes flushed immediately at exit.
                    tail = handle.read()
                    if pending or tail:
                        yield from (pending + tail).splitlines(keepends=True)
                    return
                time.sleep(0.1)

    def _read(
        self, identifier: str, process: subprocess.Popen, worker_log: Path | None = None
    ) -> None:
        assert process.stdout is not None
        try:
            lines = self._worker_lines(worker_log, process) if worker_log else process.stdout
            for line in lines:
                with self.lock:
                    text = line.rstrip("\r\n")
                    self._event(identifier, "log", {"line": text})
                    match = EPOCH.search(text)
                    if match:
                        point = {
                            "epoch": int(match[1]),
                            "train": float(match[2]),
                            "validation": float(match[3]),
                        }
                        self.records[identifier]["epoch"] = point["epoch"]
                        self.records[identifier]["history"].append(point)
                        self._save(identifier)
                        self._event(identifier, "epoch", point)
        finally:
            code = process.wait()
            with self.lock:
                record = self.records[identifier]
                record["status"] = (
                    "cancelled"
                    if record["status"] == "cancelling"
                    else "completed"
                    if code == 0
                    else "failed"
                )
                record["return_code"] = code
                record["finished_at"] = datetime.now(timezone.utc).isoformat()
                self._save(identifier)
                self._event(identifier, "state", record.copy())
                if self.job is not None:
                    self.job.close()
                    self.job = None
                self.active, self.process = None, None

    def cancel(self, identifier: str) -> dict:
        with self.lock:
            if identifier != self.active or self.process is None:
                raise ValueError("This experiment is not active")
            if self.records[identifier]["status"] == "cancelling":
                return self.records[identifier].copy()
            self.records[identifier]["status"] = "cancelling"
            self._save(identifier)
            process = self.process
            if self.job is not None:
                self.job.close()
                self.job = None
            elif os.name != "nt":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return self.records[identifier].copy()

    def history(self) -> list[dict]:
        with self.lock:
            return [record.copy() for record in reversed(list(self.records.values()))]

    def log_events(self, identifier: str, after: int) -> list[dict]:
        with self.lock:
            if identifier not in self.records:
                raise FileNotFoundError("Experiment not found")
            if identifier not in self.events:
                path = self.directory / identifier / "events.jsonl"
                self.events[identifier] = (
                    [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()][
                        -10000:
                    ]
                    if path.exists()
                    else []
                )
            return [event for event in self.events[identifier] if event["id"] > after]

    async def stream(self, identifier: str, after: int = 0):
        last_heartbeat = time.monotonic()
        while True:
            for event in self.log_events(identifier, after):
                after = event["id"]
                yield f"id: {after}\nevent: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            with self.lock:
                done = self.records[identifier]["status"] in TERMINAL
            if done:
                yield "event: end\ndata: {}\n\n"
                return
            if time.monotonic() - last_heartbeat > 10:
                yield ": heartbeat\n\n"
                last_heartbeat = time.monotonic()
            await asyncio.sleep(0.3)

    def shutdown(self) -> None:
        if self.active:
            try:
                self.cancel(self.active)
            except ValueError:
                pass  # The worker may have completed between the check and cancellation.
