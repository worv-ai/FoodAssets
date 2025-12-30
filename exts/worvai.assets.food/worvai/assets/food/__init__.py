"""Food assets and tracking utilities."""

from .core import (
    ContainerManager,
    FoodAsset,
    FoodAssetPaths,
    FoodBucketManager,
    TrackableContainer,
    get_food_asset,
    list_food_assets,
    register_food_asset,
)
from .extension import Extension, get_instance
from .items.containers import FoodBucket
from .items.edibles import PopcornAsset, PopcornBucket, PopcornBucketManager, spawn_popcorn_bucket

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
