"""
Food bucket instance with point-instanced pieces.

This module provides the FoodBucket dataclass and related utilities for spawning
food containers with physics-enabled or instanced pieces in Isaac Sim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

from isaacsim.core.utils import stage as stage_utils
from pxr import Usd, UsdGeom, UsdPhysics

from ...core.base import TrackableContainer
from ...utils import (
    SpawnBackend,
    compute_prim_bounds,
    spawn_pieces_instancer,
    spawn_physics_pieces,
    update_app,
    update_app_async,
)
from ...utils.paths import ensure_asset_exists

_logger = logging.getLogger(__name__)


def spawn_bucket(bucket_prim_path: str, usd_path: str) -> None:
    """
    Add a bucket USD reference to the stage.

    Args:
        bucket_prim_path: Target prim path for the bucket.
        usd_path: Path to the bucket USD asset file.

    Raises:
        FileNotFoundError: If the USD asset does not exist.
        RuntimeError: If no USD stage is open.
    """
    ensure_asset_exists(usd_path)
    stage = stage_utils.get_current_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    if not stage.GetPrimAtPath("/World").IsValid():
        stage.DefinePrim("/World", "Xform")
    stage_utils.add_reference_to_stage(usd_path, bucket_prim_path)
    _logger.debug("Spawned bucket at %s from %s", bucket_prim_path, usd_path)


@dataclass(frozen=True)
class FoodBucket(TrackableContainer):
    """
    Food bucket instance spawned on the stage.

    This dataclass represents a spawned food container with its pieces.
    Use the spawn() or spawn_async() class methods to create instances.
    """

    bucket_prim_path: str
    instancer_path: str
    piece_count: int
    spawn_margin: float
    enable_physics: bool = False
    piece_paths: Optional[List[str]] = None

    # -------------------------------------------------------------------------
    # TrackableContainer interface implementation
    # -------------------------------------------------------------------------

    def get_container_prim_path(self) -> str:
        """Return the USD prim path of the bucket container."""
        return self.bucket_prim_path

    def get_instancer_path(self) -> str:
        """Return the USD prim path for pieces (instancer or parent Xform)."""
        return self.instancer_path

    def get_piece_count(self) -> int:
        """Return the number of spawned pieces."""
        return self.piece_count

    def get_spawn_margin(self) -> float:
        """Return the spawn margin used during piece placement."""
        return self.spawn_margin

    # -------------------------------------------------------------------------
    # Additional public methods
    # -------------------------------------------------------------------------

    def is_physics_enabled(self) -> bool:
        """Return True if pieces were spawned with physics enabled."""
        return self.enable_physics

    def get_piece_paths(self) -> Optional[List[str]]:
        """Return individual piece prim paths (physics mode only)."""
        return self.piece_paths

    # -------------------------------------------------------------------------
    # Spawn factory methods
    # -------------------------------------------------------------------------

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
        enable_physics: bool = True,
        piece_mass: float = 0.001,
        enable_collision: bool = True,
        collision_approximation: str = "convexHull",
        enable_ccd: bool = False,
        apply_bucket_physics: bool = True,
    ) -> "FoodBucket":
        """
        Spawn a food bucket with pieces (synchronous).

        Args:
            bucket_prim_path: USD path for the bucket container.
            instancer_path: USD path for pieces (parent for physics, instancer otherwise).
            container_usd_path: Path to bucket USD file.
            piece_usd_path: Path to piece USD file.
            piece_count: Number of pieces to spawn.
            spawn_margin: Margin from bucket edges (meters).
            fill_ratio: How full the bucket is (0.0-1.0).
            seed: Random seed for reproducibility.
            update_steps: Number of app update steps after spawning.
            piece_scale: Optional scale override for pieces.
            randomize_rotation: Whether to randomize piece orientations.
            backend: Spawn backend ("numpy" or "warp").
            enable_physics: If True, spawn rigid bodies; if False, use point instancer.
            piece_mass: Mass of each piece in kg (physics mode only).
            enable_collision: Enable collision on pieces (physics mode only).
            collision_approximation: Collision shape type (physics mode only).
            enable_ccd: Enable Continuous Collision Detection (physics mode only).
            apply_bucket_physics: Apply rigid body physics to the bucket itself.

        Returns:
            A FoodBucket instance representing the spawned container.
        """
        spawn_bucket(bucket_prim_path, container_usd_path)
        update_app(update_steps)

        if apply_bucket_physics:
            cls._apply_bucket_physics(bucket_prim_path)

        piece_paths = cls._spawn_pieces(
            bucket_prim_path=bucket_prim_path,
            instancer_path=instancer_path,
            piece_usd_path=piece_usd_path,
            piece_count=piece_count,
            spawn_margin=spawn_margin,
            fill_ratio=fill_ratio,
            seed=seed,
            piece_scale=piece_scale,
            randomize_rotation=randomize_rotation,
            backend=backend,
            enable_physics=enable_physics,
            piece_mass=piece_mass,
            enable_collision=enable_collision,
            collision_approximation=collision_approximation,
            enable_ccd=enable_ccd,
        )

        update_app(update_steps)

        return cls(
            bucket_prim_path=bucket_prim_path,
            instancer_path=instancer_path,
            piece_count=piece_count,
            spawn_margin=spawn_margin,
            enable_physics=enable_physics,
            piece_paths=piece_paths,
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
        enable_physics: bool = True,
        piece_mass: float = 0.001,
        enable_collision: bool = True,
        collision_approximation: str = "convexHull",
        enable_ccd: bool = False,
        apply_bucket_physics: bool = True,
    ) -> "FoodBucket":
        """
        Spawn a food bucket with pieces (asynchronous).

        See spawn() for parameter documentation.
        """
        spawn_bucket(bucket_prim_path, container_usd_path)
        await update_app_async(update_steps)

        if apply_bucket_physics:
            cls._apply_bucket_physics(bucket_prim_path)

        piece_paths = cls._spawn_pieces(
            bucket_prim_path=bucket_prim_path,
            instancer_path=instancer_path,
            piece_usd_path=piece_usd_path,
            piece_count=piece_count,
            spawn_margin=spawn_margin,
            fill_ratio=fill_ratio,
            seed=seed,
            piece_scale=piece_scale,
            randomize_rotation=randomize_rotation,
            backend=backend,
            enable_physics=enable_physics,
            piece_mass=piece_mass,
            enable_collision=enable_collision,
            collision_approximation=collision_approximation,
            enable_ccd=enable_ccd,
        )

        await update_app_async(update_steps)

        return cls(
            bucket_prim_path=bucket_prim_path,
            instancer_path=instancer_path,
            piece_count=piece_count,
            spawn_margin=spawn_margin,
            enable_physics=enable_physics,
            piece_paths=piece_paths,
        )

    # -------------------------------------------------------------------------
    # Internal helpers (static methods)
    # -------------------------------------------------------------------------

    @staticmethod
    def _apply_bucket_physics(bucket_prim_path: str) -> None:
        """
        Apply rigid body physics and collision to the bucket.

        Args:
            bucket_prim_path: USD prim path of the bucket.

        Raises:
            RuntimeError: If no stage is open or bucket prim not found.
        """
        stage = stage_utils.get_current_stage()
        if stage is None:
            raise RuntimeError("No USD stage is open.")

        bucket_prim = stage.GetPrimAtPath(bucket_prim_path)
        if not bucket_prim.IsValid():
            raise RuntimeError(f"Bucket prim not found: {bucket_prim_path}")

        # Apply rigid body API
        rb_api = UsdPhysics.RigidBodyAPI.Apply(bucket_prim)
        rb_api.CreateRigidBodyEnabledAttr(True)

        if bucket_prim.HasAPI(UsdPhysics.CollisionAPI):
            bucket_prim.RemoveAPI(UsdPhysics.CollisionAPI)
        if bucket_prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            bucket_prim.RemoveAPI(UsdPhysics.MeshCollisionAPI)

        found_mesh = False
        # Prefer meshes already marked for collision
        for prim in Usd.PrimRange(bucket_prim):
            if not prim.IsA(UsdGeom.Mesh):
                continue
            if prim.HasAPI(UsdPhysics.CollisionAPI) or prim.HasAPI(
                UsdPhysics.MeshCollisionAPI
            ):
                found_mesh = True
                UsdPhysics.CollisionAPI.Apply(prim)
                mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(prim)
                approx_attr = mesh_collision_api.GetApproximationAttr()
                if not approx_attr:
                    approx_attr = mesh_collision_api.CreateApproximationAttr()
                approx_attr.Set("convexHull")

        # Fall back to all mesh prims if none were flagged
        if not found_mesh:
            for prim in Usd.PrimRange(bucket_prim):
                if not prim.IsA(UsdGeom.Mesh):
                    continue
                found_mesh = True
                UsdPhysics.CollisionAPI.Apply(prim)
                mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(prim)
                approx_attr = mesh_collision_api.GetApproximationAttr()
                if not approx_attr:
                    approx_attr = mesh_collision_api.CreateApproximationAttr()
                approx_attr.Set("convexHull")

        if not found_mesh:
            _logger.warning(
                "No mesh prims found for collision under %s", bucket_prim_path
            )

        _logger.debug("Applied physics to bucket at %s", bucket_prim_path)

    @staticmethod
    def _spawn_pieces(
        *,
        bucket_prim_path: str,
        instancer_path: str,
        piece_usd_path: str,
        piece_count: int,
        spawn_margin: float,
        fill_ratio: float,
        seed: Optional[int],
        piece_scale: Optional[Sequence[float]],
        randomize_rotation: bool,
        backend: Union[str, SpawnBackend, None],
        enable_physics: bool,
        piece_mass: float,
        enable_collision: bool,
        collision_approximation: str,
        enable_ccd: bool,
    ) -> Optional[List[str]]:
        """
        Spawn pieces using either physics or point instancer mode.

        Returns:
            List of piece prim paths if physics mode, None otherwise.
        """
        spawn_bounds = compute_prim_bounds(
            bucket_prim_path, spawn_margin=spawn_margin, fill_ratio=fill_ratio
        )

        if enable_physics:
            _logger.debug("Spawning %d physics pieces", piece_count)
            return spawn_physics_pieces(
                piece_count=piece_count,
                pieces_parent_path=instancer_path,
                usd_path=piece_usd_path,
                spawn_bounds=spawn_bounds,
                seed=seed,
                piece_scale=piece_scale,
                randomize_rotation=randomize_rotation,
                backend=backend,
                piece_mass=piece_mass,
                enable_collision=enable_collision,
                collision_approximation=collision_approximation,
                enable_ccd=enable_ccd,
            )
        else:
            _logger.debug("Spawning %d instanced pieces", piece_count)
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
            return None
