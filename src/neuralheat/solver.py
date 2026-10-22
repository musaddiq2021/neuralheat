"""Float32 explicit finite differences for a unit-square heat equation.

The reference is a discretized numerical solution, not analytical ground truth.
Arrays have shape (..., y, x); the solver vectorizes leading batch dimensions.
"""

import math
from dataclasses import asdict, dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float32]


@dataclass(frozen=True)
class SolverConfig:
    """Square grid including boundary nodes; dt defaults to 90% of CFL limit."""

    grid_size: int = 64
    alpha: float = 0.1
    steps: int = 120
    length: float = 1.0
    cfl_safety: float = 0.9
    dt: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.grid_size, int) or self.grid_size < 3:
            raise ValueError("grid_size must be an integer >= 3")
        if not isinstance(self.steps, int) or self.steps < 0:
            raise ValueError("steps must be a nonnegative integer")
        if not all(math.isfinite(v) and v > 0 for v in (self.alpha, self.length)):
            raise ValueError("alpha and length must be finite and positive")
        if not math.isfinite(self.cfl_safety) or not 0 < self.cfl_safety <= 1:
            raise ValueError("cfl_safety must be in (0, 1]")
        if not math.isfinite(self.time_step) or not 0 < self.time_step <= self.cfl_limit * (
            1 + 1e-12
        ):
            raise ValueError("dt must be positive and satisfy alpha*dt*(1/dx^2+1/dy^2) <= 1/2")

    @property
    def dx(self) -> float:
        return self.length / (self.grid_size - 1)

    @property
    def cfl_limit(self) -> float:
        return self.dx**2 / (4 * self.alpha)

    @property
    def time_step(self) -> float:
        return self.dt if self.dt is not None else self.cfl_safety * self.cfl_limit

    def metadata(self) -> dict:
        return {
            **asdict(self),
            "dx": self.dx,
            "effective_dt": self.time_step,
            "final_time": self.steps * self.time_step,
            "alpha_dt_over_dx2": self.alpha * self.time_step / self.dx**2,
        }


def zero_boundary(field: FloatArray) -> None:
    """Apply homogeneous Dirichlet conditions in place."""
    field[..., 0, :] = field[..., -1, :] = 0
    field[..., :, 0] = field[..., :, -1] = 0


def solve(initial: NDArray, config: SolverConfig | None = None) -> FloatArray:
    """Advance a copy of initial; enforce boundary values even for zero steps.

    Uses two reusable state buffers. The five-point stencil is O(dx^2) in
    space and explicit Euler is O(dt) in time. No clipping masks instability.
    """
    config = config if config is not None else SolverConfig()
    current = np.array(initial, dtype=np.float32, order="C", copy=True)
    if current.ndim < 2 or current.shape[-2:] != (config.grid_size, config.grid_size):
        raise ValueError(f"Expected trailing shape {(config.grid_size, config.grid_size)}")
    if not np.isfinite(current).all():
        raise ValueError("Initial temperature must be finite")
    zero_boundary(current)
    following = np.zeros_like(current)
    r = np.float32(config.alpha * config.time_step / config.dx**2)
    for _ in range(config.steps):
        center = current[..., 1:-1, 1:-1]
        following[..., 1:-1, 1:-1] = center + r * (
            current[..., 2:, 1:-1]
            + current[..., :-2, 1:-1]
            + current[..., 1:-1, 2:]
            + current[..., 1:-1, :-2]
            - 4 * center
        )
        current, following = following, current
    return current
