"""Popcorn asset implementation for worvai.assets.food."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Union

import omni.kit.app

from ...core.base import FoodAsset, FoodAssetPaths, register_food_asset
from ...core.manager import FoodBucketManager
from ...utils import SpawnBackend
from ..containers.bucket import FoodBucket
from ..definitions import POPCORN_CONTAINER, POPCORN_EDIBLE


class PopcornBucket(FoodBucket):
    """Popcorn bucket with optional overrides for future behavior."""

    pass


class PopcornBucketManager(FoodBucketManager):
    """Popcorn-specific manager for future specialization."""

    pass


class PopcornAsset(FoodAsset):
    """Popcorn food asset definition."""

    name = "popcorn"

    def get_asset_paths(self) -> FoodAssetPaths:
        """Return USD asset paths for the popcorn bucket and piece."""
        ext_manager = omni.kit.app.get_app().get_extension_manager()
        ext_path = ext_manager.get_extension_path_by_module("worvai.assets.food")
        if ext_path:
            assets_dir = Path(ext_path) / "assets"
        else:
            assets_dir = Path(__file__).resolve().parents[5] / "assets"
        return FoodAssetPaths(
            container_usd=(assets_dir / POPCORN_CONTAINER.usd).as_posix(),
            piece_usd=(assets_dir / POPCORN_EDIBLE.usd).as_posix(),
        )

    def spawn(self, **kwargs) -> PopcornBucket:
        """Spawn a popcorn bucket synchronously."""
        paths = self.get_asset_paths()
        return PopcornBucket.spawn(
            container_usd_path=paths.container_usd,
            piece_usd_path=paths.piece_usd,
            **kwargs,
        )

    async def spawn_async(self, **kwargs) -> PopcornBucket:
        """Spawn a popcorn bucket asynchronously."""
        paths = self.get_asset_paths()
        return await PopcornBucket.spawn_async(
            container_usd_path=paths.container_usd,
            piece_usd_path=paths.piece_usd,
            **kwargs,
        )


def spawn_popcorn_bucket(
    bucket_prim_path: str = "/World/PopcornBucket",
    instancer_path: str = "/World/PopcornPieces",
    piece_count: int = 50,
    spawn_margin: float = 0.02,
    fill_ratio: float = 0.6,
    seed: Optional[int] = None,
    update_steps: int = 2,
    piece_scale: Optional[Sequence[float]] = None,
    randomize_rotation: bool = True,
    backend: Union[str, SpawnBackend, None] = None,
    enable_physics: bool = True,
    piece_mass: float = 0.001,
    enable_collision: bool = True,
    collision_approximation: str = "convexHull",
    enable_ccd: bool = False,
    apply_bucket_physics: bool = True,
) -> PopcornBucket:
    """
    Spawn a popcorn bucket with physics-enabled pieces.

    Args:
        bucket_prim_path: USD path for the bucket
        instancer_path: USD path for pieces parent
        piece_count: Number of popcorn pieces
        spawn_margin: Margin from bucket edges (meters)
        fill_ratio: How full the bucket is (0.0-1.0)
        seed: Random seed
        update_steps: Update steps after spawning
        piece_scale: Optional scale override
        randomize_rotation: Randomize piece orientations
        backend: Spawn backend ("numpy" or "warp")
        enable_physics: Enable physics simulation on pieces
        piece_mass: Mass per piece in kg
        enable_collision: Enable collision on pieces
        collision_approximation: Collision shape type
        enable_ccd: Enable Continuous Collision Detection
        apply_bucket_physics: Apply physics to bucket
    """
    asset = PopcornAsset()
    return asset.spawn(
        bucket_prim_path=bucket_prim_path,
        instancer_path=instancer_path,
        piece_count=piece_count,
        spawn_margin=spawn_margin,
        fill_ratio=fill_ratio,
        seed=seed,
        update_steps=update_steps,
        piece_scale=piece_scale,
        randomize_rotation=randomize_rotation,
        backend=backend,
        enable_physics=enable_physics,
        piece_mass=piece_mass,
        enable_collision=enable_collision,
        collision_approximation=collision_approximation,
        enable_ccd=enable_ccd,
        apply_bucket_physics=apply_bucket_physics,
    )


register_food_asset(PopcornAsset())

__all__ = [
    "PopcornAsset",
    "PopcornBucket",
    "PopcornBucketManager",
    "spawn_popcorn_bucket",
]
