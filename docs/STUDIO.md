# NEURALHEAT Studio engineering notes

Studio is an adapter and visualization application. The original `solver.py`, `dataset.py`, `model.py`, `train.py`, `evaluate.py`, and `benchmark.py` are unchanged. All original reports, the reference checkpoint, and cached arrays are preserved. The backend lives in `src/neuralheat/studio/`; the browser application is in `frontend/`.

## Runtime and setup

Install the `studio` Python extra in the existing `.venv` and run `npm install` from the repository root. The root npm workspace installs dependencies declared in `frontend/package.json` and forwards build/dev/lint/typecheck/test/browser commands to the frontend. The launcher resolves both hoisted workspace packages and frontend-local packages. Use Node 24 LTS, which supports the no-child-process TypeScript scientific-logic test runner. React Flow remains a real `@xyflow/react` dependency, not a replacement graph implementation. Scientific heatmaps use a Canvas scalar renderer with numeric hover, axis coordinates, a declared linear Inferno color mapping and an adjacent numeric colorbar; plots use SVG paths through actual recorded samples. Three.js renders the optional numerical surface.

`scripts/start_dashboard.ps1` checks Python imports and frontend dependencies, detects conflicting services on ports 8000 and 5173, starts hidden local services, waits for API/UI readiness, and opens the browser. It does not install dependencies, train, regenerate data, or rerun benchmarks. It may reuse an already-running service only if its health/title identifies it as Studio. Its `finally` block stops only the process IDs it launched. Runtime logs are separate from historical scientific reports, under `.cache/studio/`.

The API uses one model instance and one device. `NEURALHEAT_DEVICE=cpu` can force CPU inference; otherwise CUDA is selected when available. A CUDA model-load failure falls back to CPU. Starting multiple uvicorn workers would allocate duplicate models; the launcher explicitly uses one. Inference and hook inspection serialize access with a shared lock, and all hooks are removed in `finally` blocks. Reports and solver requests can be served independently. CUDA memory is not allocated by the telemetry endpoint.

After `npm run build`, a subsequently started backend can also serve `frontend/dist/` at `http://127.0.0.1:8000/`; this uses the same-origin `/api` endpoints. The standard launcher uses Vite on 5173. Hash navigation keeps all pages compatible with static serving.

## API contracts

All scalar fields and source parameters are finite, bounded JSON numbers. A field request supplies either `sources` or `sample_index`. Empty sources represent a zero field. Source coordinates and widths are fractions of the checkpoint's domain length. The source amplitude uses original temperature units; no Kelvin/Celsius calibration is assumed. Arrays are row-major `[y][x]`, with row 0 at physical y=0. The renderer reverses canvas rows so the origin is lower-left.

```json
{
  "sources": [
    {"x": 0.36, "y": 0.63, "sigma": 0.085, "amplitude": 1.2}
  ],
  "frame_stride": 4
}
```

| Endpoint | Behavior |
|---|---|
| `GET /api/health` | Model availability, active experiment, inference device; no experiment start |
| `GET /api/model` | Loaded checkpoint SHA256, epoch, parameter count, dataset/scaling/physics and actual FX tensor graph |
| `GET /api/hardware` | CUDA runtime availability and device-wide `nvidia-smi` telemetry when accessible; missing values remain null |
| `GET /api/runs` | Read-only registry of reference, existing `runs/*`, and dashboard run directories |
| `GET /api/runs/{id}` | Original benchmark/evaluation/execution documents and matching saved training history |
| `GET /api/training?run_id=primary` | Saved history, without invoking the trainer |
| `GET /api/runs/{id}/logs?kind=training` | Tail of an allowlisted saved log, bounded to 200,000 characters |
| `POST /api/simulate` | Source/sample input, original solver frames, one final CNN field/error, original error metrics |
| `POST /api/infer` | Original `evaluate.predict`, including the checkpoint's input/output scaling |
| `POST /api/activations` | Field request plus `node_id`; actual channel maps, shape and statistics, module-hook summaries |
| `GET /api/experiments` | Dashboard process history; no launch |
| `POST /api/experiments` | `{"preset":"smoke"}` or `{"preset":"full"}` only; returns the unique run ID |
| `POST /api/experiments/{id}/cancel` | Stop only the manager's active owned process tree |
| `GET /api/experiments/{id}/events` | SSE events: `log`, `epoch`, `state`, `end`; event IDs support reconnection |

Requests with arbitrary commands, extra launch flags, paths, unknown presets, conflicting input modes, excessive source counts or nonfinite/out-of-bounds values are rejected. Historical run IDs are resolved through a server-owned registry, not treated as filesystem paths. Host and Origin checks restrict browser access to localhost. Endpoints have no authentication and are intended only for a trusted local workstation; do not bind to a public interface.

## Preserving scientific meaning

The solver adapter builds source fields, applies the original zero boundary function, and repeatedly calls the original solver for each requested frame interval. It never reimplements the finite-difference stencil. The final frame is tested against one original 120-step solver call. Frame stride affects playback sampling, not physics or final time. The API returns actual step indices and physical times for every frame, including a final partial interval when necessary.

Only one CNN prediction exists per simulation request, at the checkpoint's trained final step. The UI hides the prediction, error field and per-field metrics until that exact frame. It never interpolates CNN outputs or evaluates an untrained intermediate-time model. The initial panel remains fixed while the numerical panel animates. The first three visible temperature panels share their numeric range; the absolute-error panel has a separate nonnegative range. Negative CNN temperatures are retained, not clipped. Preview source fields are labeled as previews until the server applies them. Units are original arbitrary temperature units; normalized feature activations have separate labels.

The network diagram is generated from `torch.fx` tracing the actual model instance, with `ConvBlock` kept as an inspectable block. Pooling, interpolation, concatenation, the identity residual and boundary operations appear as real functional nodes. Non-tensor shape-control nodes are omitted from the visual graph. `ShapeProp` executes a real held-out input; forward hooks capture block/child-layer shapes. Selected activation maps come from that graph's actual execution, with real module forward hooks collecting summaries during the same pass. Selecting a feature channel does not rerun inference.

Historical benchmark documents are returned unchanged. The report's embedded training history takes precedence over external history, preventing a later checkpoint from silently altering an older report's optimization evidence. The UI uses recorded medians, p95, standard deviations, throughput and speedups; it does not derive new historical measurements. Percentage formatting of relative L2 is only a unit conversion. Live GPU telemetry is explicitly device-wide and separate from recorded benchmark hardware. Neither API latency nor UI rendering time is presented as scientific inference latency.

## Experiments and cancellation

The process manager constructs one fixed command from a preset:

```text
<existing .venv Python> -u scripts/run_experiment.py
  --config configs/{smoke|full}.json
  --output-root runs/studio/<timestamp-and-random-id>
```

There is no shell and no user-controlled argv, environment, or path. Python output is unbuffered. The existing runner performs its normal tests, generation, training, evaluation and benchmark. Opening Studio or selecting old reports does not run it. The manager permits only one experiment at a time. Live epoch counters and loss points are parsed from actual trainer log lines; their displayed precision is that of the logs. Completed saved histories retain the original JSON precision.

On Windows, a Job Object with `KILL_ON_JOB_CLOSE` owns the runner and descendants. Cancellation or backend process termination closes the job handle, preventing an orphaned trainer. POSIX uses a separate process session and TERM/KILL for its owned process group. The manager persists states/events under the new run directory; history survives restarts and SSE can replay bounded logs. Interrupted dashboard records are marked interrupted after restart.

Cancellation may leave an incomplete **new** cache, report or checkpoint temporary file. The existing trainer saves checkpoints atomically and the existing generator publishes cache metadata only after completion. Cancelled output remains inspectable but is not presented as a completed benchmark. Reference artifacts and earlier run outputs are not modified. A completed run does not automatically replace the loaded reference checkpoint; restart with an intentional reference model change if desired.

## Verification

The Studio API suite compares payloads against the real reference checkpoint and reports, verifies exact final solver-frame equivalence, compares activation tensors to an independent hook, checks model reuse and original normalization, exercises CPU-only missing-checkpoint operation, validates bounded requests and local access controls, and tests allowlisted process lifecycle/SSE event persistence with a harmless controlled worker. A Windows Job Object test verifies that closing ownership terminates its process promptly. Tests never start a new full or smoke experiment.

Frontend unit tests verify final-time CNN gating, numeric formatting, colormap bounds, shared field ranges, zero boundaries and source preview geometry. Browser tests use live APIs and the real checkpoint, inspect all five pages on desktop/mobile, check animation gating, source interaction, activation channels, historical report views, saved logs, and that browsing never starts an experiment. They do not click training start buttons.

Actual Studio test/build outcomes are kept separately in `reports/studio/verification.json` and `reports/studio/verification.md`; original benchmark and verification artifacts are preserved. The managed development sandbox requires a local-only temporary-directory fixture because Windows private temp-directory ACLs prevent access there; test assertions and application behavior are unchanged. Normal Windows PowerShell can run the standard `python -m pytest` command.
