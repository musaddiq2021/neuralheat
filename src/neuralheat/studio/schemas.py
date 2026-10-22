"""Bounded requests for local visualization and approved experiment presets."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    sigma: float = Field(default=0.08, ge=0.01, le=0.3)
    amplitude: float = Field(default=1.0, ge=0, le=3)


class FieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sources: list[Source] = Field(default_factory=list, max_length=12)
    sample_index: int | None = Field(default=None, ge=0, le=10000)

    @model_validator(mode="after")
    def exclusive_inputs(self) -> "FieldRequest":
        if self.sources and self.sample_index is not None:
            raise ValueError("Choose placed sources or a saved sample, not both")
        return self


class SimulationRequest(FieldRequest):
    frame_stride: int = Field(default=4, ge=1, le=120)


class ActivationRequest(FieldRequest):
    node_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_]+$")


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: Literal["smoke", "full"]
