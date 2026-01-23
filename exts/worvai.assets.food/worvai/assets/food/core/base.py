from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class FoodAssetPaths:
    container_usd: str
    piece_usd: str


class TrackableContainer(ABC):
    @abstractmethod
    def get_container_prim_path(self) -> str: ...

    @abstractmethod
    def get_instancer_path(self) -> str: ...

    @abstractmethod
    def get_piece_count(self) -> int: ...

    @abstractmethod
    def get_spawn_margin(self) -> float: ...

    def is_physics_enabled(self) -> bool:
        return False

    def get_piece_paths(self) -> Optional[List[str]]:
        return None


class FoodAsset(ABC):
    name: str

    @abstractmethod
    def get_asset_paths(self) -> FoodAssetPaths: ...

    def spawn(
        self,
        *,
        container_usd_path: Optional[str] = None,
        piece_usd_path: Optional[str] = None,
        **kwargs,
    ) -> TrackableContainer:
        from ..items.containers.bucket import FoodBucket

        paths = self.get_asset_paths()
        resolved_container = container_usd_path or paths.container_usd
        resolved_piece = piece_usd_path or paths.piece_usd
        return FoodBucket.spawn(
            container_usd_path=resolved_container,
            piece_usd_path=resolved_piece,
            **kwargs,
        )

    async def spawn_async(
        self,
        *,
        container_usd_path: Optional[str] = None,
        piece_usd_path: Optional[str] = None,
        **kwargs,
    ) -> TrackableContainer:
        from ..items.containers.bucket import FoodBucket

        paths = self.get_asset_paths()
        resolved_container = container_usd_path or paths.container_usd
        resolved_piece = piece_usd_path or paths.piece_usd
        return await FoodBucket.spawn_async(
            container_usd_path=resolved_container,
            piece_usd_path=resolved_piece,
            **kwargs,
        )


class FoodRegistry:
    def __init__(self) -> None:
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


# Global registry instance
_REGISTRY = FoodRegistry()


# -----------------------------------------------------------------------------
# Module-level convenience functions
# -----------------------------------------------------------------------------


def register_food_asset(asset: FoodAsset) -> None:
    _REGISTRY.register(asset)


def get_food_asset(name: str) -> FoodAsset:
    return _REGISTRY.get(name)


def list_food_assets() -> List[str]:
    return _REGISTRY.list_names()
