"""Popcorn asset implementation for worvai.assets.food."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Union

import omni.kit.app

from ...core.base import FoodAsset, FoodAssetPaths, register_food_asset
from ...core.manager import ContainerManager
from ...utils import SpawnBackend
from ..containers.bucket import FoodBucket
from ..definitions import POPCORN_CONTAINER, POPCORN_EDIBLE


class PopcornBucket(FoodBucket):
    """Popcorn bucket with optional overrides for future behavior."""

    pass


class PopcornBucketManager(ContainerManager):
    """Popcorn-specific manager for future specialization."""

    pass


class PopcornAsset(FoodAsset):
    name = "popcorn"

    def get_asset_paths(self) -> FoodAssetPaths:
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
        paths = self.get_asset_paths()
        return PopcornBucket.spawn(
            container_usd_path=paths.container_usd,
            piece_usd_path=paths.piece_usd,
            **kwargs,
        )

    async def spawn_async(self, **kwargs) -> PopcornBucket:
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
) -> PopcornBucket:
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
    )


register_food_asset(PopcornAsset())

__all__ = [
    "PopcornAsset",
    "PopcornBucket",
    "PopcornBucketManager",
    "spawn_popcorn_bucket",
]
