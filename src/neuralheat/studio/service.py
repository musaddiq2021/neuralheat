"""Adapters around the existing solver/model and read-only historical artifacts."""

import hashlib
import json
import logging
import subprocess
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import fx, nn
from torch.fx.passes.shape_prop import ShapeProp

from neuralheat.common import file_sha256, read_config, resolve_device, seed_everything
from neuralheat.evaluate import accuracy_metrics, load_model, predict
from neuralheat.model import ConvBlock, parameter_count
from neuralheat.solver import SolverConfig, solve, zero_boundary

from .schemas import FieldRequest, SimulationRequest

logger = logging.getLogger(__name__)


def read_optional(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return {"status": "unreadable", "error": str(error)}


class BlockTracer(fx.Tracer):
    """Keep actual ConvBlocks as graph units; expose functional skip operations."""

    def is_leaf_module(self, module: nn.Module, qualname: str) -> bool:
        return isinstance(module, ConvBlock) or super().is_leaf_module(module, qualname)


class StudioService:
    def __init__(self, root: Path, device_name: str = "auto", user_root: Path | None = None):
        self.root = root.resolve()
        self.user_root = (user_root or root).resolve()
        self.lock = threading.RLock()
        self.model: nn.Module | None = None
        self.checkpoint: dict = {}
        self.model_error: str | None = None
        self.device = resolve_device(device_name)
        self.checkpoint_path = self.root / "models/best.pt"
        self.graph_module: fx.GraphModule | None = None
        self.graph_data: dict | None = None
        self.checkpoint_hash: str | None = None
        config = read_config(self.root / "configs/full.json")
        torch.set_num_threads(min(4, torch.get_num_threads()))
        seed_everything(config["seed"])
        if self.checkpoint_path.exists():
            try:
                try:
                    if self.device.type == "cuda":
                        # Driver discovery alone does not guarantee usable CUDA
                        # kernels in a redistributed runtime. Probe once.
                        torch.zeros(1, device=self.device).add_(0)
                        torch.cuda.synchronize(self.device)
                    self.model, self.checkpoint = load_model(self.checkpoint_path, self.device)
                except RuntimeError:
                    if self.device.type != "cuda":
                        raise
                    logger.exception("CUDA model load failed; falling back to CPU")
                    self.device = torch.device("cpu")
                    self.model, self.checkpoint = load_model(self.checkpoint_path, self.device)
                self.checkpoint_hash = file_sha256(self.checkpoint_path)
                config = self.checkpoint["config"]
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                self.model_error = f"Checkpoint could not be loaded: {error}"
                logger.exception(self.model_error)
        else:
            self.model_error = "No saved models/best.pt checkpoint. Numerical simulation and saved reports remain available."
        self.config = config
        self.physics = SolverConfig(**config["physics"])

    def require_model(self) -> nn.Module:
        if self.model is None:
            raise RuntimeError(self.model_error or "Model unavailable")
        return self.model

    def initial(self, request: FieldRequest) -> tuple[np.ndarray, dict]:
        if request.sample_index is not None:
            dataset_id = self.checkpoint.get("dataset_id")
            if not dataset_id:
                raise FileNotFoundError("No checkpoint dataset is available")
            cache = self.root / "data" / dataset_id
            inputs = np.load(cache / "test_inputs.npy", mmap_mode="r", allow_pickle=False)
            if request.sample_index >= len(inputs):
                raise ValueError(f"Held-out sample index must be below {len(inputs)}")
            field = np.array(inputs[request.sample_index], dtype=np.float32, copy=True)
            return field, {
                "kind": "held_out",
                "index": request.sample_index,
                "dataset_id": dataset_id,
            }
        axis = np.linspace(0, self.physics.length, self.physics.grid_size, dtype=np.float32)
        xx, yy = np.meshgrid(axis, axis)
        field = np.zeros_like(xx)
        for source in request.sources:
            x, y, sigma = (
                source.x * self.physics.length,
                source.y * self.physics.length,
                source.sigma * self.physics.length,
            )
            field += np.asarray(
                source.amplitude * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma**2)),
                dtype=np.float32,
            )
        zero_boundary(field)
        return field, {
            "kind": "interactive_sources",
            "count": len(request.sources),
            "sources": [source.model_dump() for source in request.sources],
        }

    def infer(self, request: FieldRequest) -> dict:
        initial, provenance = self.initial(request)
        with self.lock, torch.inference_mode():
            result = predict(
                self.require_model(),
                initial[None],
                self.checkpoint["normalization_scale"],
                self.device,
            )[0]
        return {
            "prediction": result.tolist(),
            "initial": initial.tolist(),
            "trained_final_time": self.physics.steps * self.physics.time_step,
            "trained_steps": self.physics.steps,
            "device": str(self.device),
            "checkpoint_sha256": self.checkpoint_hash,
            "provenance": provenance,
            "units": "original temperature units",
        }

    def simulate(self, request: SimulationRequest) -> dict:
        initial, provenance = self.initial(request)
        frames = [{"step": 0, "time": 0.0, "field": initial.tolist()}]
        state = initial
        step = 0
        while step < self.physics.steps:
            advance = min(request.frame_stride, self.physics.steps - step)
            # Reuse the existing float32 solver, including its boundary behavior.
            state = solve(state, replace(self.physics, steps=advance))
            step += advance
            frames.append(
                {"step": step, "time": step * self.physics.time_step, "field": state.tolist()}
            )
        prediction = None
        metrics = None
        if self.model is not None:
            with self.lock, torch.inference_mode():
                prediction = predict(
                    self.model, initial[None], self.checkpoint["normalization_scale"], self.device
                )[0]
            metrics = accuracy_metrics(prediction[None], state[None])
        return {
            "initial": initial.tolist(),
            "frames": frames,
            "prediction": prediction.tolist() if prediction is not None else None,
            "absolute_error": np.abs(prediction - state).tolist()
            if prediction is not None
            else None,
            "metrics": metrics,
            "physics": self.physics.metadata(),
            "checkpoint_sha256": self.checkpoint_hash,
            "provenance": provenance,
            "prediction_valid_at_step": self.physics.steps,
            "model_error": self.model_error,
            "reference": "explicit finite-difference numerical solution; not analytical truth",
        }

    def build_graph(self) -> dict:
        with self.lock, torch.inference_mode():
            if self.graph_data is not None:
                return self.graph_data
            model = self.require_model()
            try:
                probe, provenance = self.initial(FieldRequest(sample_index=0))
            except (OSError, ValueError):
                probe, provenance = self.initial(FieldRequest())
            tensor = (
                torch.from_numpy(probe[None, None]).to(self.device)
                / self.checkpoint["normalization_scale"]
            )
            module_shapes: dict[str, list[int]] = {}
            handles = []
            for name, module in model.named_modules():
                if name:
                    handles.append(
                        module.register_forward_hook(
                            lambda _m, _a, output, key=name: module_shapes.__setitem__(
                                key, list(output.shape)
                            )
                        )
                    )
            try:
                graph = BlockTracer().trace(model)
                self.graph_module = fx.GraphModule(model, graph).eval()
                ShapeProp(self.graph_module).propagate(tensor)
            finally:
                for handle in handles:
                    handle.remove()
            nodes = []
            for node in self.graph_module.graph.nodes:
                meta = node.meta.get("tensor_meta")
                if meta is None or not hasattr(meta, "shape"):
                    continue
                module = model.get_submodule(str(node.target)) if node.op == "call_module" else None
                children = []
                if module is not None:
                    for child_name, child in module.named_children():
                        full_name = f"{node.target}.{child_name}"
                        children.append(
                            {
                                "name": full_name,
                                "type": type(child).__name__,
                                "shape": module_shapes.get(full_name),
                                "parameters": sum(p.numel() for p in child.parameters()),
                                "description": repr(child),
                            }
                        )
                shape = list(meta.shape)
                nodes.append(
                    {
                        "id": node.name,
                        "label": str(node.target) if module is not None else node.name,
                        "type": type(module).__name__ if module is not None else node.op,
                        "operation": str(node.target)
                        if node.op != "call_function"
                        else getattr(node.target, "__name__", str(node.target)),
                        "shape": shape,
                        "channels": shape[1] if len(shape) >= 2 else None,
                        "parameters": sum(p.numel() for p in module.parameters())
                        if module is not None
                        else 0,
                        "children": children,
                    }
                )
            visible = {node["id"] for node in nodes}
            edges = [
                {"id": f"{parent.name}-{node.name}", "source": parent.name, "target": node.name}
                for node in self.graph_module.graph.nodes
                if node.name in visible
                for parent in node.all_input_nodes
                if parent.name in visible
            ]
            self.graph_data = {
                "nodes": nodes,
                "edges": edges,
                "probe": provenance,
                "method": "torch.fx graph of the loaded model; tensor shapes from a real forward pass; module shapes from forward hooks",
            }
            return self.graph_data

    def activations(self, request: FieldRequest, node_id: str) -> dict:
        graph = self.build_graph()
        if node_id not in {node["id"] for node in graph["nodes"]}:
            raise ValueError("Unknown node in the loaded model graph")
        initial, provenance = self.initial(request)
        captures: dict[str, Any] = {}

        class Capture(fx.Interpreter):
            def run_node(self, node: fx.Node) -> Any:
                value = super().run_node(node)
                if node.name == node_id:
                    captures["value"] = value.detach().cpu().numpy().copy()
                return value

        with self.lock, torch.inference_mode():
            tensor = (
                torch.from_numpy(initial[None, None]).to(self.device)
                / self.checkpoint["normalization_scale"]
            )
            assert self.graph_module is not None
            # Module forward hooks collect real block and child-layer summaries
            # during the same inference; functional activations use the interpreter.
            summaries = {}
            handles = [
                module.register_forward_hook(
                    lambda _m, _a, out, key=name: summaries.__setitem__(
                        key,
                        {
                            "shape": list(out.shape),
                            "min": float(out.min().item()),
                            "max": float(out.max().item()),
                        },
                    )
                )
                for name, module in self.require_model().named_modules()
                if name
            ]
            try:
                Capture(self.graph_module).run(tensor)
            finally:
                for handle in handles:
                    handle.remove()
        value = captures["value"]
        return {
            "node_id": node_id,
            "shape": list(value.shape),
            "channels": value[0].tolist(),
            "min": float(value.min()),
            "max": float(value.max()),
            "mean": float(value.mean()),
            "std": float(value.std()),
            "provenance": provenance,
            "module_hooks": summaries,
            "units": "normalized model activations; internal features are not physical temperatures",
            "checkpoint_sha256": self.checkpoint_hash,
        }

    def metadata(self) -> dict:
        return {
            "available": self.model is not None,
            "error": self.model_error,
            "name": type(self.model).__name__ if self.model is not None else None,
            "device": str(self.device),
            "parameters": parameter_count(self.model) if self.model is not None else None,
            "checkpoint": "models/best.pt",
            "checkpoint_sha256": self.checkpoint_hash,
            "epoch": self.checkpoint.get("epoch"),
            "dataset_id": self.checkpoint.get("dataset_id"),
            "normalization_scale": self.checkpoint.get("normalization_scale"),
            "physics": self.physics.metadata(),
            "graph": self.build_graph() if self.model is not None else None,
            "test_samples": self.config["data"]["test"],
            "pytorch_version": str(torch.__version__),
            "fixed_final_time_only": True,
        }

    def catalog(self) -> dict[str, Path]:
        paths = [self.root]
        runs = self.root / "runs"
        if runs.exists():
            paths += [p for p in runs.iterdir() if p.is_dir() and (p / "reports").is_dir()]
            studio = runs / "studio"
            if studio.exists():
                paths += [p for p in studio.iterdir() if p.is_dir() and (p / "reports").is_dir()]
        if self.user_root != self.root:
            studio = self.user_root / "runs/studio"
            if studio.exists():
                paths += [p for p in studio.iterdir() if p.is_dir() and (p / "reports").is_dir()]
        return {
            "primary"
            if path == self.root
            else hashlib.sha256(self.display_path(path).encode()).hexdigest()[:12]: path
            for path in paths
            if path.resolve().is_relative_to(self.root)
            or path.resolve().is_relative_to(self.user_root)
        }

    def display_path(self, path: Path) -> str:
        if self.user_root != self.root and path.is_relative_to(self.user_root):
            return "user/" + path.relative_to(self.user_root).as_posix()
        if path.is_relative_to(self.root):
            return str(path.relative_to(self.root))
        return "user/" + path.relative_to(self.user_root).as_posix()

    def runs(self) -> list[dict]:
        result = []
        for identifier, path in self.catalog().items():
            report = read_optional(path / "reports/benchmark.json")
            execution = read_optional(path / "reports/execution.json")
            training = read_optional(path / "models/training.json")
            studio = read_optional(path / "studio.json")
            result.append(
                {
                    "id": identifier,
                    "label": f"Reference · {(report or {}).get('config_name', 'saved')}"
                    if identifier == "primary"
                    else self.display_path(path),
                    "status": (studio or report or execution or {}).get("status", "incomplete"),
                    "timestamp": (report or execution or {}).get("timestamp_utc"),
                    "has_benchmark": bool(report and report.get("status") == "completed"),
                    "has_training": training is not None,
                    "relative_path": self.display_path(path),
                }
            )
        return result

    def run(self, identifier: str) -> dict:
        path = self.catalog().get(identifier)
        if path is None:
            raise FileNotFoundError("Saved run not found")
        report = read_optional(path / "reports/benchmark.json")
        # A report's embedded training history is historical evidence. Never
        # substitute another run's current checkpoint/history into that report.
        accuracy = (report or {}).get("accuracy") or {}
        training = accuracy.get("training")
        training_note = None
        if training is None:
            candidate = read_optional(path / "models/training.json")
            if report and report.get("status") == "completed":
                expected_hash = accuracy.get("checkpoint_sha256")
                if (
                    candidate
                    and expected_hash
                    and candidate.get("checkpoint_sha256") == expected_hash
                ):
                    training = candidate
                else:
                    training_note = (
                        "No saved training history matches the historical report checkpoint."
                    )
            else:
                training = candidate
        return {
            "id": identifier,
            "benchmark": report,
            "training": training,
            "evaluation": read_optional(path / "reports/evaluation.json"),
            "execution": read_optional(path / "reports/execution.json"),
            "studio": read_optional(path / "studio.json"),
            "training_note": training_note,
        }

    def gpu_status(self) -> dict:
        gpu = None
        error = None
        try:
            process = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if __import__("os").name == "nt" else 0,
            )
            if process.returncode == 0:
                fields = [part.strip() for part in process.stdout.splitlines()[0].split(",")]

                def number(index: int) -> float | None:
                    try:
                        return float(fields[index])
                    except (ValueError, IndexError):
                        return None

                gpu = {
                    "name": fields[0],
                    "memory_used_mib": number(1),
                    "memory_total_mib": number(2),
                    "utilization_percent": number(3),
                    "temperature_c": number(4),
                }
            else:
                error = "nvidia-smi telemetry unavailable"
        except (OSError, subprocess.TimeoutExpired, IndexError):
            error = "GPU telemetry unavailable on this system"
        return {
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "inference_device": str(self.device),
            "gpu": gpu,
            "telemetry_error": error,
        }
