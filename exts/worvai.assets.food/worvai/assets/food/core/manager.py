"""Tracking utilities for containers with instanced pieces."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from isaacsim.core.utils import bounds as bounds_utils
from isaacsim.core.utils import prims as prims_utils
from isaacsim.core.utils import xforms as xforms_utils

from .base import TrackableContainer
from ..utils import get_instancer_poses


class ContainerManager:
    """Tracks container pose and item piece states."""

    def __init__(
        self,
        container: TrackableContainer,
        in_container_margin: float | None = None,
        include_container_children: bool = True,
    ) -> None:
        self._container = container
        self._in_container_margin = (
            container.get_spawn_margin()
            if in_container_margin is None
            else in_container_margin
        )
        self._include_container_children = include_container_children

    @property
    def container_prim_path(self) -> str:
        return self._container.get_container_prim_path()

    @property
    def bucket_prim_path(self) -> str:
        return self.container_prim_path

    @property
    def instancer_path(self) -> str:
        return self._container.get_instancer_path()

    @property
    def piece_count(self) -> int:
        return self._container.get_piece_count()

    def get_container_pose(self) -> Tuple[np.ndarray, np.ndarray]:
        return xforms_utils.get_world_pose(self._container.get_container_prim_path())

    def get_bucket_pose(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.get_container_pose()

    def get_piece_pose(self, piece_index: int) -> Tuple[np.ndarray, np.ndarray]:
        if not isinstance(piece_index, int):
            raise ValueError("piece_index must be an int.")
        positions, orientations = get_instancer_poses(
            self._container.get_instancer_path()
        )
        if piece_index < 0 or piece_index >= len(positions):
            raise IndexError("piece_index out of range.")
        return positions[piece_index], orientations[piece_index]

    def _get_container_bounds(self) -> np.ndarray:
        container_path = self._container.get_container_prim_path()
        if not prims_utils.is_prim_path_valid(container_path):
            raise RuntimeError(f"Container prim not found: {container_path}")
        bbox_cache = bounds_utils.create_bbox_cache()
        return bounds_utils.compute_aabb(
            bbox_cache,
            prim_path=container_path,
            include_children=self._include_container_children,
        )

    def _is_in_container(self, positions: np.ndarray, bounds: np.ndarray) -> np.ndarray:
        min_xyz = bounds[:3] - self._in_container_margin
        max_xyz = bounds[3:] + self._in_container_margin
        return np.all((positions >= min_xyz) & (positions <= max_xyz), axis=1)

    def get_piece_states(self) -> List[dict]:
        bounds = self._get_container_bounds()
        states: List[dict] = []

        positions, orientations = get_instancer_poses(
            self._container.get_instancer_path()
        )
        if len(positions) == 0:
            return states
        in_container_mask = self._is_in_container(positions, bounds)
        for idx in range(len(positions)):
            in_container = bool(in_container_mask[idx])
            states.append(
                {
                    "instance_index": idx,
                    "position": positions[idx],
                    "orientation": orientations[idx],
                    "in_container": in_container,
                    "in_bucket": in_container,
                }
            )
        return states

    def count_pieces_in_container(self) -> int:
        bounds = self._get_container_bounds()
        positions, _ = get_instancer_poses(self._container.get_instancer_path())
        if len(positions) == 0:
            return 0
        return int(self._is_in_container(positions, bounds).sum())

    def count_pieces_in_bucket(self) -> int:
        return self.count_pieces_in_container()

    def get_container_state(self) -> dict:
        position, orientation = self.get_container_pose()
        pieces_in_container = self.count_pieces_in_container()
        return {
            "prim_path": self._container.get_container_prim_path(),
            "position": position,
            "orientation": orientation,
            "pieces_total": self._container.get_piece_count(),
            "pieces_in_container": pieces_in_container,
            "pieces_in_bucket": pieces_in_container,
        }

    def get_bucket_state(self) -> dict:
        return self.get_container_state()


class FoodBucketManager(ContainerManager):
    """Bucket-focused manager for compatibility."""

    pass
