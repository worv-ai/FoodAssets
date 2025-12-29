"""Food bucket instance with point-instanced pieces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Union

from isaacsim.core.utils import stage as stage_utils

from ...core.base import TrackableContainer
from ...utils import (
    SpawnBackend,
    compute_bucket_spawn_bounds,
    spawn_pieces_instancer,
    update_app,
    update_app_async,
)


def spawn_bucket(bucket_prim_path: str, usd_path: str) -> None:
    if not Path(usd_path).is_file():
        raise FileNotFoundError(f"Missing asset at {usd_path}")
    stage = stage_utils.get_current_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    if not stage.GetPrimAtPath("/World").IsValid():
        stage.DefinePrim("/World", "Xform")
    stage_utils.add_reference_to_stage(usd_path, bucket_prim_path)


@dataclass(frozen=True)
class FoodBucket(TrackableContainer):
    """Food bucket instance spawned on the stage."""

    bucket_prim_path: str
    instancer_path: str
    piece_count: int
    spawn_margin: float

    def get_container_prim_path(self) -> str:
        return self.bucket_prim_path

    def get_instancer_path(self) -> str:
        return self.instancer_path

    def get_piece_count(self) -> int:
        return self.piece_count

    def get_spawn_margin(self) -> float:
        return self.spawn_margin

    @classmethod
    def spawn(
        cls,
        *,
        bucket_prim_path: str,
        instancer_path: str,
        container_usd_path: str,
        piece_usd_path: str,
        piece_count: int = 50,
        spawn_margin: float = 0.02,
        fill_ratio: float = 0.6,
        seed: Optional[int] = None,
        update_steps: int = 2,
        piece_scale: Optional[Sequence[float]] = None,
        randomize_rotation: bool = True,
        backend: Union[str, SpawnBackend, None] = None,
    ) -> "FoodBucket":
        spawn_bucket(bucket_prim_path, container_usd_path)
        update_app(update_steps)

        spawn_bounds = compute_bucket_spawn_bounds(
            bucket_prim_path, spawn_margin=spawn_margin, fill_ratio=fill_ratio
        )
        spawn_pieces_instancer(
            piece_count=piece_count,
            instancer_path=instancer_path,
            usd_path=piece_usd_path,
            spawn_bounds=spawn_bounds,
            seed=seed,
            piece_scale=piece_scale,
            randomize_rotation=randomize_rotation,
            backend=backend,
        )
        update_app(update_steps)

        return cls(
            bucket_prim_path=bucket_prim_path,
            instancer_path=instancer_path,
            piece_count=piece_count,
            spawn_margin=spawn_margin,
        )

    @classmethod
    async def spawn_async(
        cls,
        *,
        bucket_prim_path: str,
        instancer_path: str,
        container_usd_path: str,
        piece_usd_path: str,
        piece_count: int = 50,
        spawn_margin: float = 0.02,
        fill_ratio: float = 0.6,
        seed: Optional[int] = None,
        update_steps: int = 2,
        piece_scale: Optional[Sequence[float]] = None,
        randomize_rotation: bool = True,
        backend: Union[str, SpawnBackend, None] = None,
    ) -> "FoodBucket":
        spawn_bucket(bucket_prim_path, container_usd_path)
        await update_app_async(update_steps)

        spawn_bounds = compute_bucket_spawn_bounds(
            bucket_prim_path, spawn_margin=spawn_margin, fill_ratio=fill_ratio
        )
        spawn_pieces_instancer(
            piece_count=piece_count,
            instancer_path=instancer_path,
            usd_path=piece_usd_path,
            spawn_bounds=spawn_bounds,
            seed=seed,
            piece_scale=piece_scale,
            randomize_rotation=randomize_rotation,
            backend=backend,
        )
        await update_app_async(update_steps)

        return cls(
            bucket_prim_path=bucket_prim_path,
            instancer_path=instancer_path,
            piece_count=piece_count,
            spawn_margin=spawn_margin,
        )
