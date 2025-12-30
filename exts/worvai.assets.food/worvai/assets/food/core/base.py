"""Base abstractions for food assets."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class FoodAssetPaths:
    container_usd: str
    piece_usd: str


class TrackableContainer(ABC):
    """Abstract container interface for tracking spawned items."""

    @abstractmethod
    def get_container_prim_path(self) -> str: ...

    @abstractmethod
    def get_instancer_path(self) -> str: ...

    @abstractmethod
    def get_piece_count(self) -> int: ...

    @abstractmethod
    def get_spawn_margin(self) -> float: ...


class FoodAsset(ABC):
    """Abstract definition for a food asset."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def get_asset_paths(self) -> FoodAssetPaths: ...

    def spawn(self, **kwargs) -> TrackableContainer:
        from ..items.containers.bucket import FoodBucket

        paths = self.get_asset_paths()
        return FoodBucket.spawn(
            container_usd_path=paths.container_usd,
            piece_usd_path=paths.piece_usd,
            **kwargs,
        )

    async def spawn_async(self, **kwargs) -> TrackableContainer:
        from ..items.containers.bucket import FoodBucket

        paths = self.get_asset_paths()
        return await FoodBucket.spawn_async(
            container_usd_path=paths.container_usd,
            piece_usd_path=paths.piece_usd,
            **kwargs,
        )


class FoodRegistry:
    def __init__(self):
        self._assets: Dict[str, FoodAsset] = {}

    def register(self, asset: FoodAsset) -> None:
        self._assets[asset.name] = asset

    def get(self, name: str) -> FoodAsset:
        if name not in self._assets:
            raise KeyError(f"Unknown food asset: {name}")
        return self._assets[name]

    def list_names(self) -> List[str]:
        return sorted(self._assets.keys())

    def values(self) -> Iterable[FoodAsset]:
        return self._assets.values()


_REGISTRY = FoodRegistry()


def register_food_asset(asset: FoodAsset) -> None:
    _REGISTRY.register(asset)


def get_food_asset(name: str) -> FoodAsset:
    return _REGISTRY.get(name)


def list_food_assets() -> List[str]:
    return _REGISTRY.list_names()
