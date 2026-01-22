"""
Physics-enabled piece spawning for food assets.

This module provides functions for spawning individual rigid body pieces with
full physics simulation including collision, mass, and optional CCD support.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.core.utils import stage as stage_utils
from pxr import Gf, Usd, UsdGeom, UsdPhysics

from .backend import SpawnBackend, get_spawn_backend
from .orientation import quat_to_numpy, sample_rotations
from .paths import ensure_asset_exists

_logger = logging.getLogger(__name__)


class PhysicsPieceSpawner:
    """
    Utility class for spawning physics-enabled pieces.

    This class encapsulates the logic for creating individual rigid body pieces
    with physics properties (mass, collision, CCD, etc.).
    """

    @staticmethod
    def spawn(
        piece_count: int,
        pieces_parent_path: str,
        usd_path: str,
        spawn_bounds: Tuple[np.ndarray, np.ndarray],
        seed: Optional[int],
        piece_scale: Optional[Sequence[float]],
        randomize_rotation: bool,
        backend: Union[str, SpawnBackend, None] = None,
        piece_mass: float = 0.001,
        enable_collision: bool = True,
        collision_approximation: str = "convexHull",
        enable_ccd: bool = False,
        physics_material_path: Optional[str] = None,
    ) -> List[str]:
        """
        Spawn individual rigid body pieces with full physics simulation.

        Args:
            piece_count: Number of pieces to spawn.
            pieces_parent_path: Parent prim path to contain all pieces.
            usd_path: Path to the piece USD asset.
            spawn_bounds: (min_xyz, max_xyz) tuple defining spawn volume.
            seed: Random seed for position/rotation sampling.
            piece_scale: Optional scale override for pieces.
            randomize_rotation: Whether to randomize piece orientations.
            backend: Spawn backend ("numpy" or "warp").
            piece_mass: Mass of each piece in kg (default: 0.001 = 1 gram).
            enable_collision: Whether to enable collision on pieces.
            collision_approximation: Collision shape type ("convexHull", etc.).
            enable_ccd: Enable Continuous Collision Detection for fast-moving pieces.
            physics_material_path: Optional path to physics material to apply.

        Returns:
            List of spawned piece prim paths.

        Raises:
            FileNotFoundError: If the USD asset file does not exist.
            RuntimeError: If no USD stage is open or piece creation fails.
        """
        ensure_asset_exists(usd_path)

        stage = stage_utils.get_current_stage()
        if stage is None:
            raise RuntimeError("No USD stage is open.")

        if not stage.GetPrimAtPath("/World").IsValid():
            stage.DefinePrim("/World", "Xform")

        sim_device = PhysicsPieceSpawner._resolve_sim_device()
        enable_ccd = PhysicsPieceSpawner._normalize_ccd_for_device(
            enable_ccd, sim_device
        )
        PhysicsPieceSpawner._warn_on_collision_compatibility(
            sim_device, enable_collision, collision_approximation
        )

        # Create parent container for all pieces
        parent_prim = stage.GetPrimAtPath(pieces_parent_path)
        if not parent_prim.IsValid():
            parent_prim = stage.DefinePrim(pieces_parent_path, "Xform")

        # Sample positions and rotations
        min_xyz, max_xyz = spawn_bounds
        backend_obj = get_spawn_backend(backend)
        positions = np.asarray(
            backend_obj.sample_positions(min_xyz, max_xyz, piece_count, seed),
            dtype=np.float32,
        )

        orientations = sample_rotations(
            randomize_rotation, piece_count, backend_obj, seed
        )

        _logger.debug(
            "Spawning %d physics pieces under %s", piece_count, pieces_parent_path
        )

        piece_paths: List[str] = []

        for i in range(piece_count):
            piece_path = f"{pieces_parent_path}/piece_{i:04d}"

            # Add USD reference for the piece
            piece_prim = stage_utils.add_reference_to_stage(usd_path, piece_path)

            if not piece_prim or not piece_prim.IsValid():
                raise RuntimeError(f"Failed to create piece at {piece_path}")

            # Set transform
            xformable = UsdGeom.Xformable(piece_prim)
            pos = positions[i]
            xformable.AddTranslateOp().Set(
                Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2]))
            )

            # Set orientation
            quat = orientations[i]
            quat_np = quat_to_numpy(quat)
            # Convert to Gf.Quatf (w, x, y, z) - USD uses (real, i, j, k) = (w, x, y, z)
            gf_quat = Gf.Quatf(
                float(quat_np[0]),
                float(quat_np[1]),
                float(quat_np[2]),
                float(quat_np[3]),
            )
            xformable.AddOrientOp().Set(gf_quat)

            # Apply scale if specified
            if piece_scale:
                scale_vec = Gf.Vec3f(
                    float(piece_scale[0]), float(piece_scale[1]), float(piece_scale[2])
                )
                xformable.AddScaleOp().Set(scale_vec)

            # Apply Rigid Body physics
            rb_api = UsdPhysics.RigidBodyAPI.Apply(piece_prim)
            rb_api.CreateRigidBodyEnabledAttr(True)

            # Set mass
            mass_api = UsdPhysics.MassAPI.Apply(piece_prim)
            mass_api.CreateMassAttr(piece_mass)

            # Enable CCD if requested (helps prevent tunneling for small/fast objects)
            if enable_ccd:
                rb_api.CreateEnableCCDAttr(True)

            # Apply collision
            if enable_collision:
                PhysicsPieceSpawner._apply_collision(
                    piece_prim, collision_approximation, physics_material_path
                )

            piece_paths.append(piece_path)

        return piece_paths

    @staticmethod
    def _resolve_sim_device() -> str:
        """Return the current physics simulation device string."""
        try:
            device = SimulationManager.get_physics_sim_device()
        except Exception as exc:
            _logger.warning(
                "Failed to resolve physics sim device, assuming CPU: %s", exc
            )
            return "cpu"
        return device or "cpu"

    @staticmethod
    def _normalize_ccd_for_device(enable_ccd: bool, sim_device: str) -> bool:
        """Normalize CCD settings based on the current simulation device."""
        if enable_ccd and "cuda" in sim_device:
            _logger.warning(
                "CCD requested while GPU dynamics is enabled; CCD is disabled in GPU mode. "
                "Disabling CCD for pieces."
            )
            return False
        return enable_ccd

    @staticmethod
    def _warn_on_collision_compatibility(
        sim_device: str,
        enable_collision: bool,
        collision_approximation: str,
    ) -> None:
        """Warn about collision compatibility risks in GPU simulation."""
        if not enable_collision or "cuda" not in sim_device:
            return

        safe_approximations = {"convexHull", "boundingSphere", "boundingCube"}
        if collision_approximation in safe_approximations:
            return

        _logger.warning(
            "GPU dynamics enabled with collision approximation '%s'. Some collider types are "
            "CPU-only or unsupported in GPU mode; collisions may fall back to CPU.",
            collision_approximation,
        )

    @staticmethod
    def _apply_collision(
        piece_prim,
        collision_approximation: str,
        physics_material_path: Optional[str] = None,
    ) -> None:
        """
        Apply collision properties to a piece prim and its mesh children.

        Args:
            piece_prim: The USD prim to apply collision to.
            collision_approximation: Collision shape approximation type.
            physics_material_path: Optional physics material path to bind.
        """
        if piece_prim.HasAPI(UsdPhysics.CollisionAPI):
            piece_prim.RemoveAPI(UsdPhysics.CollisionAPI)
        if piece_prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            piece_prim.RemoveAPI(UsdPhysics.MeshCollisionAPI)

        found_mesh = False
        # Prefer meshes already marked for collision
        for prim in Usd.PrimRange(piece_prim):
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
                approx_attr.Set(collision_approximation)

        # Fall back to all mesh prims if none were flagged
        if not found_mesh:
            for prim in Usd.PrimRange(piece_prim):
                if not prim.IsA(UsdGeom.Mesh):
                    continue
                found_mesh = True
                UsdPhysics.CollisionAPI.Apply(prim)
                mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(prim)
                approx_attr = mesh_collision_api.GetApproximationAttr()
                if not approx_attr:
                    approx_attr = mesh_collision_api.CreateApproximationAttr()
                approx_attr.Set(collision_approximation)

        if not found_mesh:
            _logger.warning(
                "No mesh prims found for collision under %s", piece_prim.GetPath()
            )

        # Apply physics material if provided
        if physics_material_path:
            stage = piece_prim.GetStage()
            material_prim = stage.GetPrimAtPath(physics_material_path)
            if material_prim.IsValid():
                collision_api = UsdPhysics.CollisionAPI(piece_prim)
                # Bind physics material
                material_binding = collision_api.GetPrim().CreateRelationship(
                    "physics:material:binding"
                )
                material_binding.SetTargets([material_prim.GetPath()])


# -----------------------------------------------------------------------------
# Module-level convenience function (preserves backward compatibility)
# -----------------------------------------------------------------------------


def spawn_physics_pieces(
    piece_count: int,
    pieces_parent_path: str,
    usd_path: str,
    spawn_bounds: Tuple[np.ndarray, np.ndarray],
    seed: Optional[int],
    piece_scale: Optional[Sequence[float]],
    randomize_rotation: bool,
    backend: Union[str, SpawnBackend, None] = None,
    piece_mass: float = 0.001,
    enable_collision: bool = True,
    collision_approximation: str = "convexHull",
    enable_ccd: bool = False,
    physics_material_path: Optional[str] = None,
) -> List[str]:
    """
    Spawn individual rigid body pieces with full physics simulation.

    This is a convenience wrapper around PhysicsPieceSpawner.spawn().
    See that method for full documentation.
    """
    return PhysicsPieceSpawner.spawn(
        piece_count=piece_count,
        pieces_parent_path=pieces_parent_path,
        usd_path=usd_path,
        spawn_bounds=spawn_bounds,
        seed=seed,
        piece_scale=piece_scale,
        randomize_rotation=randomize_rotation,
        backend=backend,
        piece_mass=piece_mass,
        enable_collision=enable_collision,
        collision_approximation=collision_approximation,
        enable_ccd=enable_ccd,
        physics_material_path=physics_material_path,
    )
