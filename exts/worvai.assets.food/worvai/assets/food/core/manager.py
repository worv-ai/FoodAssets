"""
Tracking utilities for containers with instanced pieces.

This module provides managers for tracking food containers and their pieces,
computing pose and containment information during simulation.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from isaacsim.core.utils import bounds as bounds_utils
from isaacsim.core.utils import prims as prims_utils
from isaacsim.core.utils import xforms as xforms_utils

from .base import TrackableContainer
from ..utils import get_instancer_poses


class ContainerManager:
    """
    Tracks container pose and piece states for any TrackableContainer.

    This is the base manager class that provides generic container tracking
    functionality. Specialized managers (like FoodBucketManager) extend this
    with container-specific features. Supports both instanced and physics-enabled
    pieces when the container exposes piece paths.
    """

    def __init__(
        self,
        container: TrackableContainer,
        in_container_margin: Optional[float] = None,
        include_container_children: bool = True,
    ) -> None:
        """
        Initialize a container manager.

        Args:
            container: The trackable container to manage.
            in_container_margin: Margin for containment checks. If None, uses
                the container's spawn margin.
            include_container_children: Whether to include children when
                computing container bounds.
        """
        self._container = container
        self._in_container_margin = (
            container.get_spawn_margin()
            if in_container_margin is None
            else in_container_margin
        )
        self._include_container_children = include_container_children

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def container_prim_path(self) -> str:
        """Return the USD prim path of the container."""
        return self._container.get_container_prim_path()

    @property
    def instancer_path(self) -> str:
        """Return the USD prim path for pieces."""
        return self._container.get_instancer_path()

    @property
    def piece_count(self) -> int:
        """Return the total number of pieces."""
        return self._container.get_piece_count()

    # -------------------------------------------------------------------------
    # Core public methods
    # -------------------------------------------------------------------------

    def get_container_pose(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get the world pose of the container.

        Returns:
            Tuple of (position, orientation) as numpy arrays.
        """
        return xforms_utils.get_world_pose(self._container.get_container_prim_path())

    def get_piece_pose(self, piece_index: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get the world pose of a specific piece.

        Args:
            piece_index: Index of the piece to query.

        Returns:
            Tuple of (position, orientation) as numpy arrays.

        Raises:
            ValueError: If piece_index is not an int.
            IndexError: If piece_index is out of range.
        """
        if not isinstance(piece_index, int):
            raise ValueError("piece_index must be an int.")
        positions, orientations = self._get_piece_poses()
        if piece_index < 0 or piece_index >= len(positions):
            raise IndexError("piece_index out of range.")
        return positions[piece_index], orientations[piece_index]

    def get_piece_states(self) -> List[dict]:
        """
        Get state information for all pieces.

        Returns:
            List of dicts with keys: instance_index, position, orientation, in_container.
        """
        bounds = self._get_container_bounds()
        positions, orientations = self._get_piece_poses()
        if len(positions) == 0:
            return []

        in_container_mask = self._is_in_container(positions, bounds)
        return [
            {
                "instance_index": idx,
                "position": positions[idx],
                "orientation": orientations[idx],
                "in_container": bool(in_container_mask[idx]),
            }
            for idx in range(len(positions))
        ]

    def count_pieces_in_container(self) -> int:
        """
        Count how many pieces are currently inside the container bounds.

        Returns:
            Number of pieces within the container's bounding box.
        """
        bounds = self._get_container_bounds()
        positions, _ = self._get_piece_poses()
        if len(positions) == 0:
            return 0
        return int(self._is_in_container(positions, bounds).sum())

    def get_container_state(self) -> dict:
        """
        Get comprehensive state information for the container.

        Returns:
            Dict with prim_path, position, orientation, pieces_total, pieces_in_container.
        """
        position, orientation = self.get_container_pose()
        pieces_in_container = self.count_pieces_in_container()
        return {
            "prim_path": self._container.get_container_prim_path(),
            "position": position,
            "orientation": orientation,
            "pieces_total": self._container.get_piece_count(),
            "pieces_in_container": pieces_in_container,
        }

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_container_bounds(self) -> np.ndarray:
        """Compute the AABB of the container."""
        container_path = self._container.get_container_prim_path()
        if not prims_utils.is_prim_path_valid(container_path):
            raise RuntimeError(f"Container prim not found: {container_path}")
        bbox_cache = bounds_utils.create_bbox_cache()
        return bounds_utils.compute_aabb(
            bbox_cache,
            prim_path=container_path,
            include_children=self._include_container_children,
        )

    def _get_piece_poses(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get world-space positions and orientations for all pieces."""
        if self._container.is_physics_enabled():
            return self._get_physics_piece_poses()
        return get_instancer_poses(self._container.get_instancer_path())

    def _get_physics_piece_poses(self) -> Tuple[np.ndarray, np.ndarray]:
        """Resolve poses for physics-enabled pieces."""
        piece_paths = self._container.get_piece_paths()
        if not piece_paths:
            raise RuntimeError(
                "Physics-enabled container did not provide piece paths."
            )

        positions = np.zeros((len(piece_paths), 3), dtype=np.float32)
        orientations = np.zeros((len(piece_paths), 4), dtype=np.float32)

        for idx, piece_path in enumerate(piece_paths):
            if not prims_utils.is_prim_path_valid(piece_path):
                raise RuntimeError(f"Piece prim not found: {piece_path}")
            position, orientation = xforms_utils.get_world_pose(piece_path)
            positions[idx] = position
            orientations[idx] = orientation

        return positions, orientations

    def _is_in_container(self, positions: np.ndarray, bounds: np.ndarray) -> np.ndarray:
        """Check which positions are within the container bounds."""
        min_xyz = bounds[:3] - self._in_container_margin
        max_xyz = bounds[3:] + self._in_container_margin
        return np.all((positions >= min_xyz) & (positions <= max_xyz), axis=1)


class FoodBucketManager(ContainerManager):
    """
    Bucket-specific manager with convenient aliases.

    This manager extends ContainerManager with bucket-specific naming conventions.
    It provides 'bucket' aliases for generic 'container' methods, making the API
    more intuitive when working with bucket-type containers.
    """

    # -------------------------------------------------------------------------
    # Properties (bucket aliases)
    # -------------------------------------------------------------------------

    @property
    def bucket_prim_path(self) -> str:
        """Return the USD prim path of the bucket (alias for container_prim_path)."""
        return self.container_prim_path

    # -------------------------------------------------------------------------
    # Core public methods (bucket aliases)
    # -------------------------------------------------------------------------

    def get_bucket_pose(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get the world pose of the bucket (alias for get_container_pose)."""
        return self.get_container_pose()

    def get_piece_states(self) -> List[dict]:
        """
        Get piece states with 'in_bucket' alias added.

        Returns:
            List of dicts with both 'in_container' and 'in_bucket' keys.
        """
        states = super().get_piece_states()
        for state in states:
            state["in_bucket"] = state["in_container"]
        return states

    def count_pieces_in_bucket(self) -> int:
        """Count pieces in bucket (alias for count_pieces_in_container)."""
        return self.count_pieces_in_container()

    def get_bucket_state(self) -> dict:
        """
        Get bucket state with 'pieces_in_bucket' alias added.

        Returns:
            Dict with both 'pieces_in_container' and 'pieces_in_bucket' keys.
        """
        state = super().get_container_state()
        state["pieces_in_bucket"] = state["pieces_in_container"]
        return state

    def get_container_state(self) -> dict:
        """Get container state with bucket alias included."""
        return self.get_bucket_state()
