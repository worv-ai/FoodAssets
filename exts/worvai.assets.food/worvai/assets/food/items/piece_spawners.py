"""
Piece spawning utilities for food assets.

This module provides:
- USD PointInstancer spawning (optional physics).
- Physics-enabled spawning via individual rigid bodies.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple, Union

import carb
import numpy as np
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.core.utils import bounds as bounds_utils
from isaacsim.core.utils import stage as stage_utils
from pxr import Gf, Usd, UsdGeom, UsdPhysics

from ..utils.backend import SpawnBackend, get_spawn_backend
from ..utils.orientation import quat_multiply, quat_to_numpy, sample_rotations
from ..utils.paths import ensure_asset_exists

_logger = logging.getLogger(__name__)


class PiecePlacement:
    """
    Collision-aware placement helpers for spawn positions.
    """

    _RAY_DIRECTIONS: np.ndarray = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.70710678, 0.70710678, 0.0],
            [0.70710678, -0.70710678, 0.0],
        ],
        dtype=np.float32,
    )

    @classmethod
    def sample_positions_for_prim(
        cls,
        prim: Usd.Prim,
        spawn_bounds: Tuple[np.ndarray, np.ndarray],
        piece_count: int,
        seed: Optional[int],
        piece_scale: Optional[Sequence[float]],
        scale_from_prototype: bool,
        prefer_collision: bool,
        container_prim: Optional[Usd.Prim] = None,
        container_prefer_collision: bool = True,
        container_margin: Optional[float] = None,
        separation_scale: float = 2.0,
    ) -> np.ndarray:
        """
        Sample spawn positions using collider-aware bounds and spacing.

        Args:
            prim: Prototype or probe prim used for collider bounds.
            spawn_bounds: (min_xyz, max_xyz) tuple defining spawn volume.
            piece_count: Number of pieces to place.
            seed: Random seed for reproducibility.
            piece_scale: Optional scale override for pieces.
            scale_from_prototype: True if scale is already baked into the prim.
            prefer_collision: Prefer collision meshes when computing bounds.
            container_prim: Optional container prim for inside-mesh rejection.
            container_prefer_collision: Prefer collision meshes for container checks.
            container_margin: Optional margin to keep from container walls.
            separation_scale: Multiplier on the collider diameter for spacing.

        Returns:
            Array of spawn positions with shape (piece_count, 3).
        """
        min_xyz, max_xyz = spawn_bounds
        mesh_data = None
        mesh_margin = max(container_margin or 0.0, 0.0)
        if container_prim is not None and container_prim.IsValid():
            mesh_data = cls._build_mesh_ray_data(
                container_prim, container_prefer_collision
            )
            if mesh_data is None:
                _logger.warning(
                    "No mesh data available for container %s; using bounds only.",
                    container_prim.GetPath(),
                )

        if prim is None or not prim.IsValid():
            _logger.warning(
                "Invalid prim for placement; falling back to random positions."
            )
            return cls._sample_positions_with_relaxation(
                min_xyz,
                max_xyz,
                piece_count,
                seed,
                0.0,
                mesh_data=mesh_data,
                mesh_margin=mesh_margin,
            )

        radius = cls._compute_radius(
            prim, piece_scale, scale_from_prototype, prefer_collision
        )
        if container_margin is None:
            mesh_margin = max(radius, 0.0)
        else:
            mesh_margin = max(container_margin, 0.0)
        min_xyz, max_xyz = cls._shrink_bounds_for_radius(min_xyz, max_xyz, radius)
        min_distance = max(radius * separation_scale, 0.0)
        return cls._sample_positions_with_relaxation(
            min_xyz,
            max_xyz,
            piece_count,
            seed,
            min_distance,
            mesh_data=mesh_data,
            mesh_margin=mesh_margin,
        )

    @classmethod
    def _compute_radius(
        cls,
        prim: Usd.Prim,
        piece_scale: Optional[Sequence[float]],
        scale_from_prototype: bool,
        prefer_collision: bool,
    ) -> float:
        points = cls._collect_mesh_points(prim, prefer_collision)
        if points is not None and points.size > 0:
            if piece_scale and not scale_from_prototype:
                points = points * np.asarray(piece_scale, dtype=np.float32)
            center = np.mean(points, axis=0)
            radius = float(np.max(np.linalg.norm(points - center, axis=1)))
            return max(radius, 0.0)

        bounds = cls._compute_bounds(prim, prefer_collision)
        if bounds is None:
            return 0.0
        extents = np.array(bounds[3:], dtype=np.float32) - np.array(
            bounds[:3], dtype=np.float32
        )
        if not np.all(np.isfinite(extents)):
            return 0.0
        if piece_scale and not scale_from_prototype:
            extents = extents * np.asarray(piece_scale, dtype=np.float32)
        diag = float(np.linalg.norm(extents))
        return max(diag * 0.5, 0.0)

    @classmethod
    def _compute_bounds(
        cls, prim: Usd.Prim, prefer_collision: bool
    ) -> Optional[np.ndarray]:
        bbox_cache = bounds_utils.create_bbox_cache()
        bounds = cls._compute_bounds_from_meshes(prim, bbox_cache, prefer_collision)
        if bounds is None:
            bounds = bounds_utils.compute_aabb(
                bbox_cache, prim.GetPath().pathString, include_children=True
            )
        if bounds is None or len(bounds) != 6:
            return None
        if not np.all(np.isfinite(bounds)):
            return None
        return np.asarray(bounds, dtype=np.float32)

    @classmethod
    def _compute_bounds_from_meshes(
        cls, prim: Usd.Prim, bbox_cache: UsdGeom.BBoxCache, prefer_collision: bool
    ) -> Optional[np.ndarray]:
        mesh_prims = cls._collect_mesh_prims(prim, prefer_collision)
        if not mesh_prims and prefer_collision:
            mesh_prims = cls._collect_mesh_prims(prim, False)
        if not mesh_prims:
            return None

        bounds_list: List[np.ndarray] = []
        for mesh_prim in mesh_prims:
            bounds = bounds_utils.compute_aabb(
                bbox_cache, mesh_prim.GetPath().pathString, include_children=False
            )
            if bounds is None or len(bounds) != 6:
                continue
            if not np.all(np.isfinite(bounds)):
                continue
            bounds_list.append(np.asarray(bounds, dtype=np.float32))

        if not bounds_list:
            return None

        mins = np.min([b[:3] for b in bounds_list], axis=0)
        maxs = np.max([b[3:] for b in bounds_list], axis=0)
        return np.concatenate([mins, maxs])

    @classmethod
    def _collect_mesh_points(
        cls, prim: Usd.Prim, prefer_collision: bool
    ) -> Optional[np.ndarray]:
        mesh_prims = cls._collect_mesh_prims(prim, prefer_collision)
        if not mesh_prims and prefer_collision:
            mesh_prims = cls._collect_mesh_prims(prim, False)
        if not mesh_prims:
            return None

        time_code = Usd.TimeCode.Default()
        points_list: List[np.ndarray] = []
        for mesh_prim in mesh_prims:
            mesh = UsdGeom.Mesh(mesh_prim)
            points = mesh.GetPointsAttr().Get(time_code) or []
            if not points:
                continue
            xformable = UsdGeom.Xformable(mesh_prim)
            matrix = np.array(
                xformable.ComputeLocalToWorldTransform(time_code), dtype=np.float32
            )
            point_data = np.array(
                [[p[0], p[1], p[2], 1.0] for p in points], dtype=np.float32
            )
            points_list.append((point_data @ matrix.T)[:, :3])

        if not points_list:
            return None
        return np.concatenate(points_list, axis=0)

    @staticmethod
    def _collect_mesh_prims(
        root_prim: Usd.Prim, collision_only: bool
    ) -> List[Usd.Prim]:
        meshes: List[Usd.Prim] = []
        for prim in Usd.PrimRange(root_prim):
            if not prim.IsA(UsdGeom.Mesh):
                continue
            if collision_only:
                if prim.HasAPI(UsdPhysics.CollisionAPI) or prim.HasAPI(
                    UsdPhysics.MeshCollisionAPI
                ):
                    meshes.append(prim)
            else:
                meshes.append(prim)
        return meshes

    @classmethod
    def _build_mesh_ray_data(
        cls, prim: Usd.Prim, prefer_collision: bool
    ) -> Optional[dict]:
        mesh_prims = cls._collect_mesh_prims(prim, prefer_collision)
        if not mesh_prims and prefer_collision:
            mesh_prims = cls._collect_mesh_prims(prim, False)
        if not mesh_prims:
            return None

        time_code = Usd.TimeCode.Default()
        triangles: List[np.ndarray] = []
        for mesh_prim in mesh_prims:
            mesh = UsdGeom.Mesh(mesh_prim)
            points = mesh.GetPointsAttr().Get(time_code) or []
            face_counts = mesh.GetFaceVertexCountsAttr().Get(time_code) or []
            face_indices = mesh.GetFaceVertexIndicesAttr().Get(time_code) or []
            if not points or not face_counts or not face_indices:
                continue
            xformable = UsdGeom.Xformable(mesh_prim)
            matrix = np.array(
                xformable.ComputeLocalToWorldTransform(time_code), dtype=np.float32
            )
            point_data = np.array(
                [[p[0], p[1], p[2], 1.0] for p in points], dtype=np.float32
            )
            world_points = (point_data @ matrix.T)[:, :3]

            index_offset = 0
            for count in face_counts:
                if count < 3:
                    index_offset += count
                    continue
                face = face_indices[index_offset : index_offset + count]
                if len(face) < 3:
                    index_offset += count
                    continue
                v0 = world_points[face[0]]
                for idx in range(1, count - 1):
                    v1 = world_points[face[idx]]
                    v2 = world_points[face[idx + 1]]
                    triangles.append(np.stack([v0, v1, v2], axis=0))
                index_offset += count

        if not triangles:
            return None

        triangles_np = np.stack(triangles, axis=0).astype(np.float32)
        v0 = triangles_np[:, 0]
        edge1 = triangles_np[:, 1] - v0
        edge2 = triangles_np[:, 2] - v0
        return {"v0": v0, "edge1": edge1, "edge2": edge2}

    @staticmethod
    def _count_ray_intersections(
        origin: np.ndarray, direction: np.ndarray, mesh_data: dict
    ) -> int:
        v0 = mesh_data["v0"]
        edge1 = mesh_data["edge1"]
        edge2 = mesh_data["edge2"]
        eps = 1e-6
        h = np.cross(direction, edge2)
        a = np.einsum("ij,ij->i", edge1, h)
        valid = np.abs(a) > eps
        if not np.any(valid):
            return 0
        f = np.zeros_like(a)
        f[valid] = 1.0 / a[valid]
        s = origin - v0
        u = f * np.einsum("ij,ij->i", s, h)
        valid = valid & (u >= -eps) & (u <= 1.0 + eps)
        if not np.any(valid):
            return 0
        q = np.cross(s, edge1)
        v = f * np.einsum("ij,j->i", q, direction)
        valid = valid & (v >= -eps) & (u + v <= 1.0 + eps)
        if not np.any(valid):
            return 0
        t = f * np.einsum("ij,ij->i", edge2, q)
        valid = valid & (t > eps)
        return int(np.count_nonzero(valid))

    @classmethod
    def _is_point_inside_mesh(cls, point: np.ndarray, mesh_data: dict) -> bool:
        directions = cls._RAY_DIRECTIONS
        if directions.size == 0:
            return True
        jitter = np.array([0.00037, 0.00011, 0.00023], dtype=np.float32)
        hits = 0
        required_hits = max(1, int(np.ceil(len(directions) * 0.5)))
        for direction in directions:
            ray_dir = direction + jitter
            ray_dir = ray_dir / np.linalg.norm(ray_dir)
            count = cls._count_ray_intersections(point, ray_dir, mesh_data)
            if count % 2 == 1:
                hits += 1
        return hits >= required_hits

    @classmethod
    def _is_point_inside_mesh_with_margin(
        cls, point: np.ndarray, mesh_data: dict, margin: float
    ) -> bool:
        if margin <= 0.0:
            return cls._is_point_inside_mesh(point, mesh_data)
        offsets = np.array(
            [
                [0.0, 0.0, 0.0],
                [margin, 0.0, 0.0],
                [-margin, 0.0, 0.0],
                [0.0, margin, 0.0],
                [0.0, -margin, 0.0],
                [0.0, 0.0, margin],
                [0.0, 0.0, -margin],
            ],
            dtype=np.float32,
        )
        for offset in offsets:
            if not cls._is_point_inside_mesh(point + offset, mesh_data):
                return False
        return True

    @staticmethod
    def _shrink_bounds_for_radius(
        min_xyz: np.ndarray, max_xyz: np.ndarray, radius: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        if radius <= 0.0:
            return min_xyz, max_xyz
        min_adj = min_xyz + radius
        max_adj = max_xyz - radius
        if np.any(min_adj >= max_adj):
            _logger.warning(
                "Spawn bounds too small after applying piece radius; using original bounds. "
                "radius=%.4f min=%s max=%s",
                radius,
                min_xyz.tolist(),
                max_xyz.tolist(),
            )
            return min_xyz, max_xyz
        return min_adj, max_adj

    @classmethod
    def _sample_positions_with_relaxation(
        cls,
        min_xyz: np.ndarray,
        max_xyz: np.ndarray,
        count: int,
        seed: Optional[int],
        min_distance: float,
        mesh_data: Optional[dict] = None,
        mesh_margin: float = 0.0,
    ) -> np.ndarray:
        if count <= 0:
            return np.zeros((0, 3), dtype=np.float32)
        rng = np.random.default_rng(seed)
        if min_distance <= 0.0 and mesh_data is None:
            return rng.uniform(min_xyz, max_xyz, size=(count, 3)).astype(np.float32)

        positions = np.zeros((0, 3), dtype=np.float32)
        distance = min_distance
        margin = max(mesh_margin, 0.0)
        for _ in range(3):
            positions = cls._sample_separated_positions(
                min_xyz,
                max_xyz,
                count,
                distance,
                rng,
                allow_fallback=False,
                mesh_data=mesh_data,
                mesh_margin=margin,
            )
            if positions.shape[0] == count:
                return positions
            distance *= 0.9
            if margin > 0.0:
                margin *= 0.9

        if positions.shape[0] < count:
            carb.log_warn(
                "Only placed %d/%d pieces with separation %.4f; relaxing spacing."
                % (positions.shape[0], count, distance)
            )
        return cls._sample_separated_positions(
            min_xyz,
            max_xyz,
            count,
            distance,
            rng,
            allow_fallback=True,
            mesh_data=mesh_data,
            mesh_margin=margin,
        )

    @classmethod
    def _sample_separated_positions(
        cls,
        min_xyz: np.ndarray,
        max_xyz: np.ndarray,
        count: int,
        min_distance: float,
        rng: np.random.Generator,
        allow_fallback: bool,
        mesh_data: Optional[dict] = None,
        mesh_margin: float = 0.0,
    ) -> np.ndarray:
        if count <= 0:
            return np.zeros((0, 3), dtype=np.float32)
        positions: List[np.ndarray] = []
        min_dist_sq = float(min_distance * min_distance)
        max_attempts = max(30, count * 12)
        attempts = 0

        while len(positions) < count and attempts < max_attempts:
            attempts += 1
            candidate = rng.uniform(min_xyz, max_xyz)
            if mesh_data is not None:
                if not cls._is_point_inside_mesh_with_margin(
                    candidate, mesh_data, mesh_margin
                ):
                    continue
            if not positions:
                positions.append(candidate)
                continue
            existing = np.stack(positions, axis=0)
            diffs = existing - candidate
            if np.all(np.einsum("ij,ij->i", diffs, diffs) >= min_dist_sq):
                positions.append(candidate)

        if len(positions) < count and allow_fallback:
            remaining = count - len(positions)
            if mesh_data is not None:
                extra: List[np.ndarray] = []
                attempts = 0
                max_extra_attempts = max(100, remaining * 50)
                while len(extra) < remaining and attempts < max_extra_attempts:
                    attempts += 1
                    candidate = rng.uniform(min_xyz, max_xyz)
                    if cls._is_point_inside_mesh_with_margin(
                        candidate, mesh_data, mesh_margin
                    ):
                        extra.append(candidate)
                if extra:
                    positions = [*positions, *extra]
            if len(positions) < count:
                if mesh_data is not None:
                    _logger.warning(
                        "Only placed %d/%d pieces inside container; filling remaining without container checks.",
                        len(positions),
                        count,
                    )
                remaining = count - len(positions)
                fill = rng.uniform(min_xyz, max_xyz, size=(remaining, 3))
                if positions:
                    positions = [*positions, *fill]
                else:
                    positions = list(fill)

        return np.asarray(positions, dtype=np.float32)


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
    enable_physics: bool = False,
    piece_mass: float = 0.001,
    enable_collision: bool = True,
    collision_approximation: str = "convexHull",
    physics_material_path: Optional[str] = None,
    container_prim_path: Optional[str] = None,
    container_prefer_collision: bool = True,
    separation_scale: float = 2.0,
) -> str:
    """
    Spawn instanced pieces using a USD PointInstancer.

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
        enable_physics: Apply rigid body physics to the instanced prototype.
        piece_mass: Mass for instanced pieces when physics is enabled.
        enable_collision: Enable collision on instanced pieces.
        collision_approximation: Collision shape type when physics is enabled.
        physics_material_path: Optional physics material to bind.
        container_prim_path: Optional container prim path for inside-mesh rejection.
        container_prefer_collision: Prefer collision meshes for container checks.
        separation_scale: Multiplier on collider diameter for spacing between pieces.

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

    scale_from_prototype = False
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
                scale_from_prototype = True

    if enable_physics:
        rb_api = UsdPhysics.RigidBodyAPI.Apply(prototype_prim)
        rb_api.CreateRigidBodyEnabledAttr(True)

        mass_api = UsdPhysics.MassAPI.Apply(prototype_prim)
        mass_api.CreateMassAttr(piece_mass)

        if enable_collision:
            RigidBodyPieceSpawner._apply_collision(
                prototype_prim, collision_approximation, physics_material_path
            )

    container_prim = None
    if container_prim_path:
        container_prim = stage.GetPrimAtPath(container_prim_path)
        if not container_prim.IsValid():
            _logger.warning(
                "Container prim not found for placement: %s", container_prim_path
            )
            container_prim = None

    backend_obj = get_spawn_backend(backend)
    positions = PiecePlacement.sample_positions_for_prim(
        prototype_prim,
        spawn_bounds,
        piece_count,
        seed,
        piece_scale,
        scale_from_prototype,
        prefer_collision=enable_collision,
        container_prim=container_prim,
        container_prefer_collision=container_prefer_collision,
        separation_scale=separation_scale,
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
        container_prim_path: Optional[str] = None,
        container_prefer_collision: bool = True,
        separation_scale: float = 2.0,
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
            container_prim_path: Optional container prim path for inside-mesh rejection.
            container_prefer_collision: Prefer collision meshes for container checks.
            separation_scale: Multiplier on collider diameter for spacing between pieces.

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

        container_prim = None
        if container_prim_path:
            container_prim = stage.GetPrimAtPath(container_prim_path)
            if not container_prim.IsValid():
                _logger.warning(
                    "Container prim not found for placement: %s", container_prim_path
                )
                container_prim = None

        probe_path = f"{pieces_parent_path}/_bounds_probe"
        probe_prim = stage_utils.add_reference_to_stage(usd_path, probe_path)
        positions = PiecePlacement.sample_positions_for_prim(
            probe_prim,
            spawn_bounds,
            piece_count,
            seed,
            piece_scale,
            False,
            prefer_collision=enable_collision,
            container_prim=container_prim,
            container_prefer_collision=container_prefer_collision,
            separation_scale=separation_scale,
        )
        stage.RemovePrim(probe_path)

        backend_obj = get_spawn_backend(backend)
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
