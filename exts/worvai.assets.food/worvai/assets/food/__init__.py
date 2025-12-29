"""Food assets and tracking utilities."""

from .core import (
    ContainerManager,
    FoodAsset,
    FoodAssetPaths,
    TrackableContainer,
    get_food_asset,
    list_food_assets,
    register_food_asset,
)
from .extension import Extension, get_instance
from .core import FoodBucketManager
from .items.edibles import PopcornAsset, PopcornBucket, PopcornBucketManager, spawn_popcorn_bucket
from .items.containers import FoodBucket

__all__ = [
    "Extension",
    "FoodAsset",
    "FoodAssetPaths",
    "TrackableContainer",
    "ContainerManager",
    "FoodBucket",
    "FoodBucketManager",
    "PopcornAsset",
    "PopcornBucket",
    "PopcornBucketManager",
    "get_food_asset",
    "get_instance",
    "list_food_assets",
    "register_food_asset",
    "spawn_popcorn_bucket",
]
