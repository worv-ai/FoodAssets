"""
Structured definitions for food assets (paths, scales, mass).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Mapping, Optional, Tuple


@dataclass(frozen=True)
class BaseItemDefinition(ABC):
    """Shared definition for item assets."""

    USD_EXTENSIONS: ClassVar[Tuple[str, ...]] = (".usd", ".usda", ".usdc")
    DEFAULT_SCALE: ClassVar[Tuple[float, float, float]] = (1.0, 1.0, 1.0)

    name: str
    usd: str
    scale: Tuple[float, float, float] = DEFAULT_SCALE
    mass_kg: Optional[float] = None

    @property
    @abstractmethod
    def kind(self) -> str: ...

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not self.usd or not self.usd.endswith(self.USD_EXTENSIONS):
            raise ValueError(f"usd path must end with {self.USD_EXTENSIONS}: {self.usd!r}")
        if len(self.scale) != 3:
            raise ValueError("scale must be a 3-tuple")
        if any(value <= 0 for value in self.scale):
            raise ValueError("scale values must be > 0")
        if self.mass_kg is not None and self.mass_kg <= 0:
            raise ValueError("mass_kg must be > 0 when provided")


@dataclass(frozen=True)
class ContainerDefinition(BaseItemDefinition):
    """Definition for container assets (e.g., bucket, plate)."""

    @property
    def kind(self) -> str:
        return "container"


@dataclass(frozen=True)
class EdibleDefinition(BaseItemDefinition):
    """Definition for edible assets (e.g., popcorn, taco)."""

    @property
    def kind(self) -> str:
        return "edible"


POPCORN_CONTAINER = ContainerDefinition(
    name="popcorn_bucket",
    usd="popcorn-bucket.usdc",
)

POPCORN_EDIBLE = EdibleDefinition(
    name="popcorn",
    usd="popcorn.usdc",
)

TACO_EDIBLE = EdibleDefinition(
    name="taco",
    usd="taco.usdc",
)

CONTAINERS: Mapping[str, ContainerDefinition] = {
    POPCORN_CONTAINER.name: POPCORN_CONTAINER,
}

EDIBLES: Mapping[str, EdibleDefinition] = {
    POPCORN_EDIBLE.name: POPCORN_EDIBLE,
    TACO_EDIBLE.name: TACO_EDIBLE,
}

POPCORN_CONTAINER_USD = POPCORN_CONTAINER.usd
POPCORN_PIECE_USD = POPCORN_EDIBLE.usd
TACO_PIECE_USD = TACO_EDIBLE.usd

__all__ = [
    "CONTAINERS",
    "EDIBLES",
    "BaseItemDefinition",
    "ContainerDefinition",
    "EdibleDefinition",
    "POPCORN_CONTAINER",
    "POPCORN_CONTAINER_USD",
    "POPCORN_EDIBLE",
    "POPCORN_PIECE_USD",
    "TACO_EDIBLE",
    "TACO_PIECE_USD",
]
