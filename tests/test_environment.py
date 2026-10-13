"""Tests for WallEEnvironment, physics model, and configuration."""

import math
import unittest
from walle.config import ClueData, MapConfig, MissionConfig, ResourceConfig, SensorConfig
from walle.environment import ActionType, MissionStatus, WallEEnvironment


class TestWallEEnvironment(unittest.TestCase):

    def setUp(self):
        self.map_config = MapConfig(
            width=10,
            height=10,
            walle_start=(1, 1),
            eve_position=(8, 8),
            eve_status="DORMANT_REBOOT_REQUIRED",
            obstacles=[(2, 1), (5, 5)],
            recharge_stations=[(1, 2)],
            clues=[
                ClueData(
                    id="clue_01",
                    x=1,
                    y=0,
                    description="Ion signature heading South-East.",
                    clue_type="heading",
                    payload={"bearing_range": [90, 180]}
                )
            ]
        )
        self.config = MissionConfig(
            name="Test Mission",
            description="Unit test environment configuration",
            map_config=self.map_config,
            resources=ResourceConfig(
                initial_battery=50,
                max_battery=50,
                max_time_ticks=50,
                move_cost=2,
                scan_cost=4,
                inspect_cost=3,
                recharge_rate=10
            ),
            sensor=SensorConfig(
                p0=-20.0,
                eta=2.0,
                rssi_noise_std=0.0,  # Zero noise for deterministic testing
                bearing_noise_std_deg=0.0
            ),
            seed=42
        )
        self.env = WallEEnvironment(self.config, seed=42)

    def test_reset(self):
        obs = self.env.reset()
        self.assertEqual(obs.position, (1, 1))
        self.assertEqual(obs.battery, 50)
        self.assertEqual(obs.time_tick, 0)
        self.assertIsNotNone(obs.rssi)
        self.assertIsNotNone(obs.bearing_deg)
        self.assertEqual(obs.mission_status, MissionStatus.IN_PROGRESS)

    def test_move_success(self):
        self.env.reset()
        # Move South from (1, 1) -> (1, 2)
        obs, meta = self.env.step(ActionType.MOVE_S)
        self.assertEqual(obs.position, (1, 2))
        self.assertEqual(obs.battery, 48)
        self.assertEqual(obs.time_tick, 1)
        self.assertTrue(obs.at_recharge_station)

    def test_obstacle_collision(self):
        self.env.reset()
        # Obstacle at (2, 1); try moving East from (1, 1)
        obs, meta = self.env.step(ActionType.MOVE_E)
        self.assertEqual(obs.position, (1, 1))  # Did not move into obstacle
        self.assertFalse(meta["success"])
        self.assertEqual(obs.battery, 48)  # Still costs battery to attempt move

    def test_boundary_collision(self):
        self.env.reset()
        # Try moving North from (1, 0) - first move to (1, 0)
        self.env.step(ActionType.MOVE_N)  # At (1, 0)
        obs, meta = self.env.step(ActionType.MOVE_N)  # Boundary at y=-1
        self.assertEqual(obs.position, (1, 0))
        self.assertFalse(meta["success"])

    def test_recharge_at_station(self):
        self.env.reset()
        # Move South to (1, 2) which is a recharge station
        self.env.step(ActionType.MOVE_S)
        # Drain battery first
        self.env.battery = 20
        obs, meta = self.env.step(ActionType.RECHARGE)
        self.assertEqual(obs.battery, 30)
        self.assertTrue(obs.at_recharge_station)

    def test_clue_inspection(self):
        self.env.reset()
        # Clue is at (1, 0). WALL-E is at (1, 1), which is adjacent!
        obs, meta = self.env.step(ActionType.INSPECT)
        self.assertIsNotNone(obs.inspected_clue)
        self.assertEqual(obs.inspected_clue["id"], "clue_01")
        self.assertIn("clue_01", self.env.discovered_clues)

    def test_signal_physics(self):
        self.env.reset()
        # Distance from (1, 1) to (8, 8): dx=7, dy=7 -> dist = sqrt(98) ~ 9.899
        # Obstacle at (5, 5) lies directly along the LOS from (1, 1) to (8, 8) (-4.0 dB attenuation)
        dist = math.sqrt(7**2 + 7**2)
        expected_rssi = -20.0 - 10.0 * 2.0 * math.log10(dist) - 4.0
        expected_bearing = math.degrees(math.atan2(7, 7))  # 45 degrees
        rssi, bearing = self.env._compute_signal((1, 1))
        self.assertAlmostEqual(rssi, expected_rssi, places=2)
        self.assertAlmostEqual(bearing, expected_bearing, places=2)

    def test_battery_depletion_failure(self):
        self.env.reset()
        self.env.battery = 2
        obs, meta = self.env.step(ActionType.MOVE_S)
        self.assertEqual(obs.mission_status, MissionStatus.FAILED_BATTERY_DEPLETED)


if __name__ == "__main__":
    unittest.main()
