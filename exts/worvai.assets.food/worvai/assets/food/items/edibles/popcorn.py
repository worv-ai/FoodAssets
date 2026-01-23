from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Optional, Sequence, Union

from ...core.base import FoodAsset, FoodAssetPaths, register_food_asset
from ...core.manager import FoodBucketManager
from ...utils import SpawnBackend
from ..containers.bucket import FoodBucket
from ..definitions import POPCORN_CONTAINER, POPCORN_EDIBLE


class PopcornBucket(FoodBucket):
    pass


class PopcornBucketManager(FoodBucketManager):
    pass


class PopcornAsset(FoodAsset):
    name = "popcorn"

    def get_asset_paths(self) -> FoodAssetPaths:
        ext_manager = import_module("omni.kit.app").get_app().get_extension_manager()
        ext_path = ext_manager.get_extension_path_by_module("worvai.assets.food")
        if ext_path:
            assets_dir = Path(ext_path) / "assets"
        else:
            assets_dir = Path(__file__).resolve().parents[5] / "assets"
        return FoodAssetPaths(
            container_usd=(assets_dir / POPCORN_CONTAINER.usd).as_posix(),
            piece_usd=(assets_dir / POPCORN_EDIBLE.usd).as_posix(),
        )

    def spawn(
        self,
        *,
        container_usd_path: Optional[str] = None,
        piece_usd_path: Optional[str] = None,
        **kwargs,
    ) -> FoodBucket:
        paths = self.get_asset_paths()
        resolved_container = container_usd_path or paths.container_usd
        resolved_piece = piece_usd_path or paths.piece_usd
        return PopcornBucket.spawn(
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
    ) -> FoodBucket:
        paths = self.get_asset_paths()
        resolved_container = container_usd_path or paths.container_usd
        resolved_piece = piece_usd_path or paths.piece_usd
        return await PopcornBucket.spawn_async(
            container_usd_path=resolved_container,
            piece_usd_path=resolved_piece,
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
    enable_instancer_physics: bool = False,
    piece_mass: float = 0.001,
    enable_collision: bool = True,
    collision_approximation: str = "convexHull",
    enable_ccd: bool = False,
    apply_bucket_physics: bool = True,
    physics_material_path: Optional[str] = None,
    container_usd_path: Optional[str] = None,
    piece_usd_path: Optional[str] = None,
) -> FoodBucket:
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
        enable_instancer_physics=enable_instancer_physics,
        piece_mass=piece_mass,
        enable_collision=enable_collision,
        collision_approximation=collision_approximation,
        enable_ccd=enable_ccd,
        apply_bucket_physics=apply_bucket_physics,
        physics_material_path=physics_material_path,
        container_usd_path=container_usd_path,
        piece_usd_path=piece_usd_path,
    )


register_food_asset(PopcornAsset())

__all__ = [
    "PopcornAsset",
    "PopcornBucket",
    "PopcornBucketManager",
    "spawn_popcorn_bucket",
]
