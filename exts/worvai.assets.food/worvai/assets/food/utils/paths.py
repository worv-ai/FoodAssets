"""Path helpers for food asset USD files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse


def _is_omniverse_path(usd_path: str) -> bool:
    return usd_path.startswith("omniverse://")


def _local_path_from_uri(usd_path: str) -> Optional[Path]:
    if _is_omniverse_path(usd_path):
        return None
    if usd_path.startswith("file:"):
        parsed = urlparse(usd_path)
        if parsed.scheme != "file":
            return None
        local_path = unquote(parsed.path)
        if parsed.netloc:
            local_path = f"/{local_path.lstrip('/')}"
        return Path(local_path)
    return Path(usd_path)


def asset_exists(usd_path: str) -> bool:
    """Return True if a USD asset exists locally or on Nucleus."""
    if _is_omniverse_path(usd_path):
        try:
            import omni.client
        except Exception:
            return False
        result, _ = omni.client.stat(usd_path)
        return result == omni.client.Result.OK

    local_path = _local_path_from_uri(usd_path)
    if local_path is None:
        return False
    return local_path.is_file()


def ensure_asset_exists(usd_path: str) -> None:
    """Raise if the USD asset does not exist."""
    if not asset_exists(usd_path):
        raise FileNotFoundError(f"Missing asset at {usd_path}")
