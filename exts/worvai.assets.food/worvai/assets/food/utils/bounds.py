"""Bounds helpers for food assets."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from isaacsim.core.utils import bounds as bounds_utils
from isaacsim.core.utils import stage as stage_utils
from pxr import UsdGeom


def compute_safe_bounds(
    prim_path: str, bbox_cache: Optional[UsdGeom.BBoxCache] = None
) -> Tuple[np.ndarray, bool]:
    """Compute a prim AABB and report if the bounds are valid."""
    stage = stage_utils.get_current_stage()
    if stage is None:
        raise RuntimeError("No active stage found.")

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise ValueError(f"Prim not found: {prim_path}")

    if bbox_cache is None:
        bbox_cache = bounds_utils.create_bbox_cache()

    max_float32 = np.finfo(np.float32).max
    invalid_threshold = max_float32 * 0.9

    bounds = bounds_utils.compute_aabb(bbox_cache, prim_path, include_children=True)
    if bounds is None or len(bounds) != 6:
        return bounds, False
    if not np.all(np.isfinite(bounds)):
        return bounds, False
    if bool(np.any(np.abs(bounds) >= invalid_threshold)):
        return bounds, False
    return bounds, True


def compute_prim_bounds(
    prim_path: str, spawn_margin: float, fill_ratio: float
) -> Tuple[np.ndarray, np.ndarray]:
    if spawn_margin < 0.0:
        raise ValueError("spawn_margin must be >= 0")
    if fill_ratio <= 0.0 or fill_ratio > 1.0:
        raise ValueError("fill_ratio must be in (0, 1]")

    bbox_cache = bounds_utils.create_bbox_cache()
    bounds, is_valid = compute_safe_bounds(prim_path, bbox_cache)
    if not is_valid:
        stage = stage_utils.get_current_stage()
        if stage is None:
            raise RuntimeError("No active stage found.")
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise ValueError(f"Prim not found: {prim_path}")

        valid_child_bounds: List[np.ndarray] = []
        for child in prim.GetChildren():
            child_path = child.GetPath().pathString
            child_bounds, child_valid = compute_safe_bounds(child_path, bbox_cache)
            if child_valid:
                valid_child_bounds.append(child_bounds)

        if not valid_child_bounds:
            raise ValueError(
                "Bounds computation failed. The prim and all its children "
                "returned infinite or empty bounds. Ensure the USD has valid geometry. "
                f"prim={prim_path!r}"
            )

        mins = np.min([b[:3] for b in valid_child_bounds], axis=0)
        maxs = np.max([b[3:] for b in valid_child_bounds], axis=0)
        bounds = np.concatenate([mins, maxs])

    min_xyz = bounds[:3] + spawn_margin
    max_xyz = bounds[3:] - spawn_margin
    full_height = max_xyz[2] - min_xyz[2]
    max_xyz[2] = min_xyz[2] + (full_height * fill_ratio)

    if np.any(min_xyz >= max_xyz):
        invalid_axes = []
        for axis, idx in (("x", 0), ("y", 1), ("z", 2)):
            if min_xyz[idx] >= max_xyz[idx]:
                invalid_axes.append(axis)
        raise ValueError(
            "Computed spawn bounds are invalid; reduce spawn_margin or fill_ratio. "
            f"prim={prim_path!r} bounds={bounds.tolist()} "
            f"spawn_margin={spawn_margin} fill_ratio={fill_ratio} "
            f"min_xyz={min_xyz.tolist()} max_xyz={max_xyz.tolist()} "
            f"invalid_axes={','.join(invalid_axes) if invalid_axes else 'unknown'}"
        )
    return min_xyz, max_xyz
