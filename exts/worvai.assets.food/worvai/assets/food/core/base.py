"""
Base abstractions for food assets.

This module defines the core abstract interfaces and data structures used
throughout the food assets extension:
- FoodAssetPaths: Immutable container for USD asset paths
- TrackableContainer: Interface for containers that can be tracked
- FoodAsset: Abstract definition for a spawnable food asset
- FoodRegistry: Central registry for available food assets
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class FoodAssetPaths:
    """
    Immutable container for food asset USD file paths.

    Attributes:
        container_usd: Path to the container USD file (e.g., bucket).
        piece_usd: Path to the individual piece USD file (e.g., popcorn kernel).
    """

    container_usd: str
    piece_usd: str


class TrackableContainer(ABC):
    """
    Abstract interface for containers with spawned pieces.

    Implementations must provide methods for querying container state,
    enabling tracking of pieces during simulation. Containers that spawn
    physics-enabled pieces can override is_physics_enabled() and
    get_piece_paths() to enable per-piece tracking.
    """

    @abstractmethod
    def get_container_prim_path(self) -> str:
        """Return the USD prim path of the container."""

    @abstractmethod
    def get_instancer_path(self) -> str:
        """Return the USD prim path for pieces (instancer or parent Xform)."""

    @abstractmethod
    def get_piece_count(self) -> int:
        """Return the number of spawned pieces."""

    @abstractmethod
    def get_spawn_margin(self) -> float:
        """Return the spawn margin used during piece placement."""

    def is_physics_enabled(self) -> bool:
        """
        Return True if pieces were spawned with physics enabled.

        Defaults to False for instancer-only containers.
        """
        return False

    def get_piece_paths(self) -> Optional[List[str]]:
        """
        Return individual piece prim paths for physics containers.

        Defaults to None for instancer-only containers.
        """
        return None


class FoodAsset(ABC):
    """
    Abstract definition for a spawnable food asset.

    Subclasses must implement the name property and get_asset_paths() method.
    The spawn() and spawn_async() methods provide default implementations
    that delegate to FoodBucket.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this food asset."""

    @abstractmethod
    def get_asset_paths(self) -> FoodAssetPaths:
        """Return the USD file paths for this asset."""

    def spawn(self, **kwargs) -> TrackableContainer:
        """
        Spawn this food asset synchronously.

        Args:
            **kwargs: Passed to FoodBucket.spawn().

        Returns:
            A TrackableContainer representing the spawned asset.
        """
        from ..items.containers.bucket import FoodBucket

        paths = self.get_asset_paths()
        return FoodBucket.spawn(
            container_usd_path=paths.container_usd,
            piece_usd_path=paths.piece_usd,
            **kwargs,
        )

    async def spawn_async(self, **kwargs) -> TrackableContainer:
        """
        Spawn this food asset asynchronously.

        Args:
            **kwargs: Passed to FoodBucket.spawn_async().

        Returns:
            A TrackableContainer representing the spawned asset.
        """
        from ..items.containers.bucket import FoodBucket

        paths = self.get_asset_paths()
        return await FoodBucket.spawn_async(
            container_usd_path=paths.container_usd,
            piece_usd_path=paths.piece_usd,
            **kwargs,
        )


class FoodRegistry:
    """
    Registry for available food assets.

    Provides registration, lookup, and enumeration of food assets.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._assets: Dict[str, FoodAsset] = {}

    def register(self, asset: FoodAsset) -> None:
        """
        Register a food asset.

        Args:
            asset: The asset to register (keyed by asset.name).
        """
        self._assets[asset.name] = asset

    def get(self, name: str) -> FoodAsset:
        """
        Get a registered asset by name.

        Args:
            name: The asset name.

        Returns:
            The registered FoodAsset.

        Raises:
            KeyError: If no asset with that name is registered.
        """
        if name not in self._assets:
            raise KeyError(f"Unknown food asset: {name}")
        return self._assets[name]

    def list_names(self) -> List[str]:
        """Return a sorted list of all registered asset names."""
        return sorted(self._assets.keys())

    def values(self) -> Iterable[FoodAsset]:
        """Return an iterable of all registered assets."""
        return self._assets.values()


# Global registry instance
_REGISTRY = FoodRegistry()


# -----------------------------------------------------------------------------
# Module-level convenience functions
# -----------------------------------------------------------------------------


def register_food_asset(asset: FoodAsset) -> None:
    """Register a food asset in the global registry."""
    _REGISTRY.register(asset)


def get_food_asset(name: str) -> FoodAsset:
    """Get a food asset from the global registry by name."""
    return _REGISTRY.get(name)


def list_food_assets() -> List[str]:
    """List all registered food asset names."""
    return _REGISTRY.list_names()
