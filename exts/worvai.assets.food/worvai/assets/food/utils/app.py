"""App update helpers for food assets."""

from __future__ import annotations

import omni.kit.app


def update_app(steps: int) -> None:
    """Advance the Isaac Sim app by a number of update steps."""
    if steps <= 0:
        return
    app = omni.kit.app.get_app()
    for _ in range(steps):
        app.update()


async def update_app_async(steps: int) -> None:
    """Advance the Isaac Sim app asynchronously by a number of update steps."""
    if steps <= 0:
        return
    app = omni.kit.app.get_app()
    for _ in range(steps):
        await app.next_update_async()
