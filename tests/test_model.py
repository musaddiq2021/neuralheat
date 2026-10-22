import pytest

torch = pytest.importorskip("torch")
from neuralheat.common import seed_everything
from neuralheat.model import HeatUNet, parameter_count


@pytest.mark.parametrize("size", [63, 64])
def test_shape_exact_boundaries_and_initial_identity(size: int) -> None:
    torch.set_num_threads(1)
    model = HeatUNet(base_channels=2).eval()
    initial = torch.rand(2, 1, size, size)
    with torch.inference_mode():
        result = model(initial)
    assert result.shape == initial.shape
    assert torch.isfinite(result).all()
    assert torch.count_nonzero(result[..., 0, :]) == 0
    assert torch.count_nonzero(result[..., -1, :]) == 0
    assert torch.count_nonzero(result[..., :, 0]) == 0
    assert torch.count_nonzero(result[..., :, -1]) == 0
    torch.testing.assert_close(result[..., 1:-1, 1:-1], initial[..., 1:-1, 1:-1])
    assert 0 < parameter_count(model) < 100_000


def test_backward_is_finite_and_can_learn_correction() -> None:
    model = HeatUNet(base_channels=2)
    initial = torch.rand(2, 1, 16, 16)
    loss = model(initial).square().mean()
    loss.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    assert model.head.weight.grad.abs().sum() > 0


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA runtime not available")
def test_cuda_backward_with_deterministic_algorithms() -> None:
    seed_everything(42)
    model = HeatUNet(base_channels=2).to("cuda")
    initial = torch.rand(2, 1, 16, 16, device="cuda")
    model(initial).square().mean().backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
