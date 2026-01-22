"""
Piece spawning utilities for food assets.

This module provides:
- Visual-only spawning via USD PointInstancer.
- Physics-enabled spawning via individual rigid bodies.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.core.utils import stage as stage_utils
from pxr import Gf, Usd, UsdGeom, UsdPhysics

from ..utils.backend import SpawnBackend, get_spawn_backend
from ..utils.orientation import quat_multiply, quat_to_numpy, sample_rotations
from ..utils.paths import ensure_asset_exists

_logger = logging.getLogger(__name__)


def spawn_point_instancer_pieces(
    piece_count: int,
    instancer_path: str,
    usd_path: str,
    spawn_bounds: Tuple[np.ndarray, np.ndarray],
    seed: Optional[int],
    piece_scale: Optional[Sequence[float]],
    randomize_rotation: bool,
    backend: Union[str, SpawnBackend, None] = None,
    prototype_path: Optional[str] = None,
) -> str:
    """
    Spawn instanced pieces using a USD PointInstancer (visual only).

    Args:
        piece_count: Number of pieces to spawn.
        instancer_path: USD path for the PointInstancer prim.
        usd_path: Path to the piece USD asset.
        spawn_bounds: (min_xyz, max_xyz) tuple defining spawn volume.
        seed: Random seed for reproducibility.
        piece_scale: Optional scale override for pieces.
        randomize_rotation: Whether to randomize piece orientations.
        backend: Spawn backend ("numpy" or "warp").
        prototype_path: Optional path for the prototype prim.

    Returns:
        The instancer prim path.

    Raises:
        RuntimeError: If no USD stage is open.
        ValueError: If a non-instancer prim exists at the path.
    """
    ensure_asset_exists(usd_path)
    stage = stage_utils.get_current_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    if not stage.GetPrimAtPath("/World").IsValid():
        stage.DefinePrim("/World", "Xform")

    prototype_path = prototype_path or f"{instancer_path}_Prototype"

    instancer_prim = stage.GetPrimAtPath(instancer_path)
    if instancer_prim.IsValid() and not instancer_prim.IsA(UsdGeom.PointInstancer):
        raise ValueError(f"Prim at {instancer_path} is not a PointInstancer.")
    if not instancer_prim.IsValid():
        instancer_prim = stage.DefinePrim(instancer_path, "PointInstancer")

    instancer = UsdGeom.PointInstancer(instancer_prim)
    prototype_prim = stage_utils.add_reference_to_stage(usd_path, prototype_path)
    instancer.CreatePrototypesRel().SetTargets([prototype_prim.GetPath()])

    if piece_scale is None:
        xformable = UsdGeom.Xformable(prototype_prim)
        if xformable:
            local_transform = xformable.GetLocalTransformation()
            scale_vec = Gf.Transform(local_transform).GetScale()
            proto_scale = (
                float(scale_vec[0]),
                float(scale_vec[1]),
                float(scale_vec[2]),
            )
            if np.all(np.isfinite(proto_scale)) and not np.allclose(proto_scale, 1.0):
                piece_scale = proto_scale

    min_xyz, max_xyz = spawn_bounds
    backend_obj = get_spawn_backend(backend)
    positions = np.asarray(
        backend_obj.sample_positions(min_xyz, max_xyz, piece_count, seed),
        dtype=np.float32,
    )
    proto_indices = [0] * piece_count

    instancer.CreatePositionsAttr().Set(
        [Gf.Vec3f(float(pos[0]), float(pos[1]), float(pos[2])) for pos in positions]
    )
    instancer.CreateProtoIndicesAttr().Set(proto_indices)

    orientations = sample_rotations(randomize_rotation, piece_count, backend_obj, seed)
    instancer.CreateOrientationsAttr().Set(orientations)

    if piece_scale:
        scale_vec = Gf.Vec3f(
            float(piece_scale[0]), float(piece_scale[1]), float(piece_scale[2])
        )
        instancer.CreateScalesAttr().Set([scale_vec for _ in range(piece_count)])

    _logger.debug(
        "Created point instancer at %s with %d pieces", instancer_path, piece_count
    )
    return instancer_path


def get_point_instancer_poses(instancer_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Get world-space positions and orientations of all point-instanced pieces.

    Args:
        instancer_path: USD path to the PointInstancer prim.

    Returns:
        Tuple of (positions, orientations) arrays:
        - positions: Shape (N, 3), world-space XYZ positions.
        - orientations: Shape (N, 4), quaternions as (w, x, y, z).

    Raises:
        RuntimeError: If no stage is open or prim not found.
        ValueError: If the prim is not a PointInstancer.
    """
    stage = stage_utils.get_current_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    prim = stage.GetPrimAtPath(instancer_path)
    if not prim.IsValid():
        raise RuntimeError(f"Instancer prim not found: {instancer_path}")
    if not prim.IsA(UsdGeom.PointInstancer):
        raise ValueError(f"Prim at {instancer_path} is not a PointInstancer.")
    instancer = UsdGeom.PointInstancer(prim)
    positions_attr = instancer.GetPositionsAttr()
    positions = positions_attr.Get() or []

    orientations_attr = instancer.GetOrientationsAttr()
    orientations = orientations_attr.Get() if orientations_attr else []
    if orientations is None or len(orientations) == 0:
        identity = Gf.Quath()
        orientations = [identity for _ in range(len(positions))]

    xformable = UsdGeom.Xformable(prim)
    world_matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    world_matrix_np = np.array(world_matrix, dtype=np.float32)
    instancer_rotation = world_matrix.ExtractRotation().GetQuat()
    instancer_quat = quat_to_numpy(instancer_rotation)

    pos_np = np.array([[p[0], p[1], p[2]] for p in positions], dtype=np.float32)
    if len(pos_np) == 0:
        return pos_np, np.zeros((0, 4), dtype=np.float32)

    pos_h = np.concatenate(
        [pos_np, np.ones((pos_np.shape[0], 1), dtype=np.float32)], axis=1
    )
    world_pos = (pos_h @ world_matrix_np.T)[:, :3]

    ori_np = np.zeros((len(orientations), 4), dtype=np.float32)
    for idx, quat in enumerate(orientations):
        local_quat = quat_to_numpy(quat)
        ori_np[idx] = quat_multiply(instancer_quat, local_quat)

    return world_pos, ori_np


class RigidBodyPieceSpawner:
    """
    Utility class for spawning rigid body pieces.

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

        sim_device = RigidBodyPieceSpawner._resolve_sim_device()
        enable_ccd = RigidBodyPieceSpawner._normalize_ccd_for_device(
            enable_ccd, sim_device
        )
        RigidBodyPieceSpawner._warn_on_collision_compatibility(
            sim_device, enable_collision, collision_approximation
        )

        parent_prim = stage.GetPrimAtPath(pieces_parent_path)
        if not parent_prim.IsValid():
            parent_prim = stage.DefinePrim(pieces_parent_path, "Xform")

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
            "Spawning %d rigid body pieces under %s", piece_count, pieces_parent_path
        )

        piece_paths: List[str] = []

        for i in range(piece_count):
            piece_path = f"{pieces_parent_path}/piece_{i:04d}"

            piece_prim = stage_utils.add_reference_to_stage(usd_path, piece_path)

            if not piece_prim or not piece_prim.IsValid():
                raise RuntimeError(f"Failed to create piece at {piece_path}")

            xformable = UsdGeom.Xformable(piece_prim)
            pos = positions[i]
            xformable.AddTranslateOp().Set(
                Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2]))
            )

            quat = orientations[i]
            quat_np = quat_to_numpy(quat)
            gf_quat = Gf.Quatf(
                float(quat_np[0]),
                float(quat_np[1]),
                float(quat_np[2]),
                float(quat_np[3]),
            )
            xformable.AddOrientOp().Set(gf_quat)

            if piece_scale:
                scale_vec = Gf.Vec3f(
                    float(piece_scale[0]), float(piece_scale[1]), float(piece_scale[2])
                )
                xformable.AddScaleOp().Set(scale_vec)

            rb_api = UsdPhysics.RigidBodyAPI.Apply(piece_prim)
            rb_api.CreateRigidBodyEnabledAttr(True)

            mass_api = UsdPhysics.MassAPI.Apply(piece_prim)
            mass_api.CreateMassAttr(piece_mass)

            if enable_ccd:
                rb_api.CreateEnableCCDAttr(True)

            if enable_collision:
                RigidBodyPieceSpawner._apply_collision(
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

        if physics_material_path:
            stage = piece_prim.GetStage()
            material_prim = stage.GetPrimAtPath(physics_material_path)
            if material_prim.IsValid():
                collision_api = UsdPhysics.CollisionAPI(piece_prim)
                material_binding = collision_api.GetPrim().CreateRelationship(
                    "physics:material:binding"
                )
                material_binding.SetTargets([material_prim.GetPath()])


__all__ = [
    "spawn_point_instancer_pieces",
    "get_point_instancer_poses",
    "RigidBodyPieceSpawner",
]
