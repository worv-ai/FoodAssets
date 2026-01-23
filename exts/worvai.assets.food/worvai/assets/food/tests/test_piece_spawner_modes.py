import omni.kit.test

from worvai.assets.food.items.piece_spawners import RigidBodyPieceSpawner


class TestPieceSpawnerModes(omni.kit.test.AsyncTestCase):
    async def test_ccd_cpu_enabled(self):
        enabled = RigidBodyPieceSpawner._normalize_ccd_for_device(True, "cpu")
        self.assertTrue(enabled)

    async def test_ccd_gpu_disabled(self):
        enabled = RigidBodyPieceSpawner._normalize_ccd_for_device(True, "cuda")
        self.assertFalse(enabled)

    async def test_ccd_gpu_off_stays_off(self):
        enabled = RigidBodyPieceSpawner._normalize_ccd_for_device(False, "cuda")
        self.assertFalse(enabled)

    async def test_collision_warning_gpu_mesh(self):
        logger_name = "worvai.assets.food.items.piece_spawners"
        with self.assertLogs(logger_name, level="WARNING") as context:
            RigidBodyPieceSpawner._warn_on_collision_compatibility(
                "cuda", True, "meshSimplification"
            )
        self.assertTrue(
            any("collision approximation" in message for message in context.output)
        )

    async def test_collision_no_warning_cpu(self):
        RigidBodyPieceSpawner._warn_on_collision_compatibility(
            "cpu", True, "meshSimplification"
        )
