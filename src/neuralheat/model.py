"""Small residual U-Net with two spatial reductions and exact zero edges."""

import torch
from torch import nn
from torch.nn import functional as F


class ConvBlock(nn.Sequential):
    def __init__(self, incoming: int, outgoing: int):
        super().__init__(
            nn.Conv2d(incoming, outgoing, 3, padding=1),
            nn.GELU(),
            nn.Conv2d(outgoing, outgoing, 3, padding=1),
            nn.GELU(),
        )


class HeatUNet(nn.Module):
    """Learn the diffusion correction to an identity baseline.

    Channels b -> 2b -> 4b, average pooling, nearest-neighbor upsampling, and
    concatenated encoder skips. A linear head permits signed corrections.
    The final boundary projection enforces the specified Dirichlet condition.
    """

    def __init__(self, base_channels: int = 8):
        super().__init__()
        if base_channels < 1:
            raise ValueError("base_channels must be positive")
        b = base_channels
        self.encoder1 = ConvBlock(1, b)
        self.encoder2 = ConvBlock(b, 2 * b)
        self.bottleneck = ConvBlock(2 * b, 4 * b)
        self.decoder2 = ConvBlock(6 * b, 2 * b)
        self.decoder1 = ConvBlock(3 * b, b)
        self.head = nn.Conv2d(b, 1, 1)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)

    def forward(self, initial: torch.Tensor) -> torch.Tensor:
        first = self.encoder1(initial)
        second = self.encoder2(F.avg_pool2d(first, 2))
        latent = self.bottleneck(F.avg_pool2d(second, 2))
        decoded = self.decoder2(
            torch.cat(
                [F.interpolate(latent, size=second.shape[-2:], mode="nearest"), second], dim=1
            )
        )
        decoded = self.decoder1(
            torch.cat([F.interpolate(decoded, size=first.shape[-2:], mode="nearest"), first], dim=1)
        )
        result = initial + self.head(decoded)
        return F.pad(result[..., 1:-1, 1:-1], (1, 1, 1, 1))


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())
