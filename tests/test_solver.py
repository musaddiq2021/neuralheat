import pytest

np = pytest.importorskip("numpy")
from neuralheat.solver import SolverConfig, solve


def test_cfl_and_reject_unstable_step() -> None:
    physics = SolverConfig()
    assert physics.alpha * physics.time_step / physics.dx**2 == pytest.approx(0.225)
    with pytest.raises(ValueError, match="dt"):
        SolverConfig(dt=physics.cfl_limit * 1.01)


@pytest.mark.parametrize(
    "kwargs",
    [{"alpha": 0}, {"length": float("nan")}, {"steps": -1}, {"grid_size": 2}, {"cfl_safety": 1.1}],
)
def test_invalid_configuration(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        SolverConfig(**kwargs)


def test_zero_input() -> None:
    np.testing.assert_array_equal(solve(np.zeros((64, 64))), 0)


def test_boundaries_batch_equivalence_and_input_ownership() -> None:
    physics = SolverConfig(grid_size=17, steps=12)
    initial = np.random.default_rng(3).random((3, 17, 17), dtype=np.float32)
    original = initial.copy()
    result = solve(initial, physics)
    for edge in (result[..., 0, :], result[..., -1, :], result[..., :, 0], result[..., :, -1]):
        assert np.count_nonzero(edge) == 0
    np.testing.assert_array_equal(initial, original)
    np.testing.assert_array_equal(result, np.stack([solve(field, physics) for field in initial]))
    assert result.dtype == np.float32


def test_maximum_principle_at_cfl_limit_long_run() -> None:
    physics = SolverConfig(grid_size=32, steps=500, cfl_safety=1.0)
    initial = np.random.default_rng(1).uniform(-2, 3, (32, 32)).astype(np.float32)
    result = solve(initial, physics)
    assert np.isfinite(result).all()
    assert result.min() >= initial.min() - 1e-6
    assert result.max() <= initial.max() + 1e-6
    assert np.linalg.norm(result) < np.linalg.norm(initial)


def test_impulse_symmetry_peak_and_diffusion() -> None:
    physics = SolverConfig(grid_size=65, steps=30)
    initial = np.zeros((65, 65), dtype=np.float32)
    initial[32, 32] = 1
    result = solve(initial, physics)
    np.testing.assert_allclose(result, result.T, atol=2e-8)
    np.testing.assert_allclose(result, result[::-1], atol=2e-8)
    assert 0 < result[32, 32] < 1
    assert result[32, 33] > 0
    yy, xx = np.indices(result.shape)
    variance = np.sum(result * ((xx - 32) ** 2 + (yy - 32) ** 2)) / result.sum()
    assert variance > 1
    assert result.sum() == pytest.approx(1, abs=2e-6)


def test_dirichlet_heat_loss() -> None:
    initial = np.ones((64, 64), dtype=np.float32)
    initial[[0, -1]] = 0
    initial[:, [0, -1]] = 0
    result = solve(initial)
    assert 0 < result.sum() < initial.sum()
    assert result.min() >= 0


def test_discrete_eigenmode_amplification() -> None:
    physics = SolverConfig(grid_size=33, steps=50)
    axis = np.linspace(0, 1, 33)
    initial = np.outer(np.sin(np.pi * axis), np.sin(2 * np.pi * axis)).astype(np.float32)
    r = physics.alpha * physics.time_step / physics.dx**2
    gain = 1 - 4 * r * (np.sin(np.pi / (2 * 32)) ** 2 + np.sin(2 * np.pi / (2 * 32)) ** 2)
    expected = initial * gain**physics.steps
    np.testing.assert_allclose(solve(initial, physics), expected, atol=5e-7)


def test_refinement_against_continuum_sine_solution() -> None:
    errors = []
    for n, steps in [(17, 20), (33, 80)]:
        physics = SolverConfig(grid_size=n, steps=steps)
        axis = np.linspace(0, 1, n)
        initial = np.outer(np.sin(np.pi * axis), np.sin(np.pi * axis)).astype(np.float32)
        analytical = initial * np.exp(-2 * np.pi**2 * physics.alpha * physics.time_step * steps)
        errors.append(np.max(np.abs(solve(initial, physics) - analytical)))
    assert 3.5 < errors[0] / errors[1] < 4.5


def test_invalid_input_and_zero_step_projection() -> None:
    with pytest.raises(ValueError, match="shape"):
        solve(np.ones((3, 3)))
    with pytest.raises(ValueError, match="finite"):
        solve(np.full((64, 64), np.nan))
    result = solve(np.ones((64, 64)), SolverConfig(steps=0))
    assert result[0, 0] == 0 and result[32, 32] == 1
