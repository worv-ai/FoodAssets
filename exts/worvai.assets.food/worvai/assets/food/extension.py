"""Food assets UI + API extension."""

from __future__ import annotations

import asyncio
from typing import Optional, Tuple

import carb
import omni.ext
import omni.kit.actions.core
import omni.kit.menu.utils as menu_utils
import omni.ui as ui
from isaacsim.gui.components.widgets import DynamicComboBoxModel
from omni.kit.menu.utils import MenuItemDescription

from .core import ContainerManager, get_food_asset, list_food_assets
from .items.containers import FoodBucket

_EXTENSION_NAME = "worvai.assets.food"
_MENU_ROOT = "WoRV"
_MENU_ITEM = "Food"
_WINDOW_TITLE = "Food"

_INSTANCE: Optional["Extension"] = None


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id: str):
        global _INSTANCE
        _INSTANCE = self
        self._ext_id = ext_id
        self._bucket: Optional[FoodBucket] = None
        self._manager: Optional[ContainerManager] = None
        self._menu_items = []
        self._window = ui.Window(
            _WINDOW_TITLE,
            width=360,
            height=460,
            visible=False,
            dockPreference=ui.DockPreference.LEFT_BOTTOM,
        )
        self._window.set_visibility_changed_fn(self._on_window_visibility_changed)
        self._build_models()
        self._build_ui()
        self._register_actions()
        self._add_menu()

    def on_shutdown(self):
        self._remove_menu()
        self._deregister_actions()
        self._window = None
        self._bucket = None
        self._manager = None
        global _INSTANCE
        _INSTANCE = None

    def spawn_food(self, food_name: str = "popcorn", **kwargs) -> FoodBucket:
        asset = get_food_asset(food_name)
        bucket = asset.spawn(**kwargs)
        self._bucket = bucket
        self._manager = None
        return bucket

    async def spawn_food_async(
        self, food_name: str = "popcorn", **kwargs
    ) -> FoodBucket:
        asset = get_food_asset(food_name)
        bucket = await asset.spawn_async(**kwargs)
        self._bucket = bucket
        self._manager = None
        return bucket

    def create_manager(self, bucket: Optional[FoodBucket] = None) -> ContainerManager:
        bucket = bucket or self._bucket
        if bucket is None:
            raise RuntimeError("No food bucket has been spawned yet.")
        manager = ContainerManager(bucket)
        self._manager = manager
        return manager

    def spawn_and_track(self, food_name: str = "popcorn", **kwargs) -> ContainerManager:
        bucket = self.spawn_food(food_name, **kwargs)
        return self.create_manager(bucket)

    async def spawn_and_track_async(
        self, food_name: str = "popcorn", **kwargs
    ) -> ContainerManager:
        bucket = await self.spawn_food_async(food_name, **kwargs)
        return self.create_manager(bucket)

    def _register_actions(self) -> None:
        action_registry = omni.kit.actions.core.get_action_registry()
        action_registry.register_action(
            _EXTENSION_NAME,
            "toggle_food_window",
            self._toggle_window,
            display_name="Toggle Food window",
            description="Show or hide the Food window",
            tag="WoRV",
        )

    def _deregister_actions(self) -> None:
        action_registry = omni.kit.actions.core.get_action_registry()
        action_registry.deregister_all_actions_for_extension(_EXTENSION_NAME)

    def _add_menu(self) -> None:
        self._menu_items = [
            MenuItemDescription(
                name=_MENU_ITEM,
                ticked=True,
                ticked_fn=self._is_window_visible,
                onclick_action=(_EXTENSION_NAME, "toggle_food_window"),
            )
        ]
        menu_utils.add_menu_items(self._menu_items, _MENU_ROOT, menu_index=-1)
        menu_utils.refresh_menu_items(_MENU_ROOT)

    def _remove_menu(self) -> None:
        if not self._menu_items:
            return
        menu_utils.remove_menu_items(self._menu_items, _MENU_ROOT)
        self._menu_items = []

    def _is_window_visible(self) -> bool:
        return bool(self._window and self._window.visible)

    def _toggle_window(self) -> None:
        if self._window is None:
            return
        self._window.visible = not self._window.visible

    def _on_window_visibility_changed(self, _visible: bool) -> None:
        menu_utils.refresh_menu_items(_MENU_ROOT)

    def _build_models(self) -> None:
        assets = list_food_assets()
        default_food = assets[0] if assets else "popcorn"
        self._food_name_model = ui.SimpleStringModel(default_food)
        self._available_items = assets or ["None"]
        self._available_model = DynamicComboBoxModel(self._available_items)
        self._backend_items = ["numpy", "warp"]
        self._backend_model = DynamicComboBoxModel(self._backend_items)
        self._bucket_path_model = ui.SimpleStringModel(
            self._default_bucket_path(default_food)
        )
        self._instancer_path_model = ui.SimpleStringModel(
            self._default_instancer_path(default_food)
        )
        self._piece_count_model = ui.SimpleIntModel(50)
        self._spawn_margin_model = ui.SimpleFloatModel(0.02)
        self._fill_ratio_model = ui.SimpleFloatModel(0.6)
        self._update_steps_model = ui.SimpleIntModel(2)
        self._seed_model = ui.SimpleStringModel("")
        self._randomize_rotation_model = ui.SimpleBoolModel(True)
        self._status_model = ui.SimpleStringModel("Ready")

    def _build_ui(self) -> None:
        with self._window.frame:
            with ui.VStack(spacing=8, height=0):
                ui.Label("Food Assets")
                with ui.HStack():
                    ui.Label("Available", width=140)
                    self._available_combo = ui.ComboBox(self._available_model)
                self._available_combo.model.add_item_changed_fn(
                    self._on_available_selection
                )
                with ui.HStack():
                    ui.Label("Food name", width=140)
                    ui.StringField(self._food_name_model)
                with ui.HStack():
                    ui.Label("Backend", width=140)
                    self._backend_combo = ui.ComboBox(self._backend_model)
                with ui.HStack():
                    ui.Label("Bucket prim", width=140)
                    ui.StringField(self._bucket_path_model)
                with ui.HStack():
                    ui.Label("Instancer prim", width=140)
                    ui.StringField(self._instancer_path_model)
                with ui.HStack():
                    ui.Label("Piece count", width=140)
                    ui.IntField(self._piece_count_model)
                with ui.HStack():
                    ui.Label("Spawn margin", width=140)
                    ui.FloatField(self._spawn_margin_model)
                with ui.HStack():
                    ui.Label("Fill ratio", width=140)
                    ui.FloatField(self._fill_ratio_model)
                with ui.HStack():
                    ui.Label("Update steps", width=140)
                    ui.IntField(self._update_steps_model)
                with ui.HStack():
                    ui.Label("Seed (optional)", width=140)
                    ui.StringField(self._seed_model)
                with ui.HStack():
                    ui.Label("Random rotation", width=140)
                    ui.CheckBox(self._randomize_rotation_model)

                ui.Spacer(height=4)
                with ui.HStack():
                    ui.Button("Spawn", clicked_fn=self._on_spawn_clicked)
                    ui.Button("Spawn + Track", clicked_fn=self._on_spawn_track_clicked)
                with ui.HStack():
                    ui.Button(
                        "Create Manager", clicked_fn=self._on_create_manager_clicked
                    )
                    ui.Button(
                        "Refresh Assets", clicked_fn=self._on_refresh_assets_clicked
                    )
                with ui.HStack():
                    ui.Label("Status", width=140)
                    ui.StringField(self._status_model, read_only=True, width=ui.Fraction(1))
        self._sync_available_selection()

    def _default_bucket_path(self, food_name: str) -> str:
        token = food_name.replace("_", " ").title().replace(" ", "")
        token = token or "Food"
        return f"/World/{token}Bucket"

    def _default_instancer_path(self, food_name: str) -> str:
        token = food_name.replace("_", " ").title().replace(" ", "")
        token = token or "Food"
        return f"/World/{token}Pieces"

    def _get_selected_available_name(self) -> Optional[str]:
        index = self._available_model.get_item_value_model().as_int
        if 0 <= index < len(self._available_items):
            name = self._available_items[index]
            if name != "None":
                return name
        return None

    def _get_selected_backend(self) -> Optional[str]:
        index = self._backend_model.get_item_value_model().as_int
        if 0 <= index < len(self._backend_items):
            return self._backend_items[index]
        return None

    def _apply_food_name(self, food_name: str) -> None:
        food_name = food_name.strip()
        if not food_name:
            return
        current_name = self._food_name_model.get_value_as_string().strip() or food_name
        current_bucket = self._bucket_path_model.get_value_as_string().strip()
        current_instancer = self._instancer_path_model.get_value_as_string().strip()
        self._food_name_model.set_value(food_name)
        if not current_bucket or current_bucket == self._default_bucket_path(current_name):
            self._bucket_path_model.set_value(self._default_bucket_path(food_name))
        if not current_instancer or current_instancer == self._default_instancer_path(current_name):
            self._instancer_path_model.set_value(self._default_instancer_path(food_name))

    def _sync_available_selection(self) -> None:
        if not self._available_items or self._available_combo is None:
            return
        food_name = self._food_name_model.get_value_as_string().strip()
        try:
            index = self._available_items.index(food_name)
        except ValueError:
            index = 0
        self._available_combo.model.set_item_value_model(ui.SimpleIntModel(index))

    def _collect_spawn_settings(self) -> Tuple[str, dict]:
        food_name = self._food_name_model.get_value_as_string().strip() or "popcorn"
        backend = self._get_selected_backend()
        bucket_prim_path = self._bucket_path_model.get_value_as_string().strip()
        instancer_path = self._instancer_path_model.get_value_as_string().strip()
        if not bucket_prim_path:
            bucket_prim_path = self._default_bucket_path(food_name)
        if not instancer_path:
            instancer_path = self._default_instancer_path(food_name)

        seed_text = self._seed_model.get_value_as_string().strip()
        seed = int(seed_text) if seed_text else None

        settings = {
            "bucket_prim_path": bucket_prim_path,
            "instancer_path": instancer_path,
            "piece_count": int(self._piece_count_model.get_value_as_int()),
            "spawn_margin": float(self._spawn_margin_model.get_value_as_float()),
            "fill_ratio": float(self._fill_ratio_model.get_value_as_float()),
            "seed": seed,
            "update_steps": int(self._update_steps_model.get_value_as_int()),
            "randomize_rotation": bool(
                self._randomize_rotation_model.get_value_as_bool()
            ),
            "backend": backend,
        }
        return food_name, settings

    def _set_status(self, message: str) -> None:
        self._status_model.set_value(message)

    def _on_available_selection(self, _model=None, _item=None) -> None:
        selected = self._get_selected_available_name()
        if selected:
            self._apply_food_name(selected)

    def _on_spawn_clicked(self) -> None:
        asyncio.ensure_future(self._spawn_from_ui(track=False))

    def _on_spawn_track_clicked(self) -> None:
        asyncio.ensure_future(self._spawn_from_ui(track=True))

    def _on_create_manager_clicked(self) -> None:
        try:
            self.create_manager()
        except Exception as exc:
            carb.log_error(f"Food manager creation failed: {exc}")
            self._set_status(f"Error: {exc}")
            return
        self._set_status("Manager created.")

    def _on_refresh_assets_clicked(self) -> None:
        assets = list_food_assets()
        self._available_items = assets or ["None"]
        self._available_model = DynamicComboBoxModel(self._available_items)
        self._available_combo.model = self._available_model
        self._available_combo.model.add_item_changed_fn(self._on_available_selection)
        self._sync_available_selection()
        self._set_status("Assets refreshed.")

    async def _spawn_from_ui(self, track: bool) -> None:
        try:
            self._set_status("Spawning...")
            food_name, settings = self._collect_spawn_settings()
            if track:
                await self.spawn_and_track_async(food_name, **settings)
                self._set_status(f"Spawned and tracking {food_name}.")
            else:
                await self.spawn_food_async(food_name, **settings)
                self._set_status(f"Spawned {food_name}.")
        except Exception as exc:
            carb.log_error(f"Food spawn failed: {exc}")
            self._set_status(f"Error: {exc}")


def get_instance() -> Optional[Extension]:
    return _INSTANCE
