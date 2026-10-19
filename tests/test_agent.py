"""Unit tests for GridPlanner and AutonomousWallEAgent."""

import unittest
from walle.agent import AutonomousWallEAgent
from walle.config import ClueData, MapConfig, MissionConfig, ResourceConfig, SensorConfig
from walle.environment import ActionType, MissionStatus, Observation
from walle.planner import GridPlanner


class TestPlannerAndAgent(unittest.TestCase):

    def setUp(self):
        self.map_config = MapConfig(
            width=10,
            height=10,
            walle_start=(1, 1),
            eve_position=(8, 8),
            obstacles=[(1, 2), (2, 2)],  # Wall blocking south
            recharge_stations=[(1, 0)],
            clues=[
                ClueData(id="c1", x=2, y=1, description="Nearby clue", clue_type="general")
            ]
        )
        self.config = MissionConfig(
            name="Agent Test",
            description="Testing agent logic",
            map_config=self.map_config,
            resources=ResourceConfig(
                initial_battery=100,
                max_battery=100,
                move_cost=2,
                safety_margin=6
            ),
            sensor=SensorConfig(rssi_noise_std=0.1, bearing_noise_std_deg=1.0)
        )
        self.planner = GridPlanner(10, 10, self.config.resources)
        self.agent = AutonomousWallEAgent(self.config)

    def test_astar_around_obstacle(self):
        # From (1, 1) to (1, 3). Direct South is blocked by (1, 2).
        # A* must path around via East (2, 1 is free, wait, (2, 2) is obstacle, so (0, 1) or (3, 1))
        obstacles = {(1, 2), (2, 2)}
        res = self.planner.astar((1, 1), (1, 3), obstacles)
        self.assertTrue(res.found)
        self.assertNotIn((1, 2), res.path)
        self.assertNotIn((2, 2), res.path)
        self.assertEqual(res.path[0], (1, 1))
        self.assertEqual(res.path[-1], (1, 3))

    def test_battery_critical_safety_check(self):
        # Station at (1, 0). Current pos (1, 4). Distance = 4 steps.
        # Cost = 4 * 2 = 8 battery. Safety margin = 6. Threshold = 14.
        obstacles = set()
        is_crit, cost, station = self.planner.check_battery_safety(
            (1, 4), current_battery=14, stations={(1, 0)}, known_obstacles=obstacles
        )
        self.assertTrue(is_crit)
        self.assertEqual(station, (1, 0))
        self.assertEqual(cost, 8)

        # If battery is 20, not critical
        is_crit, _, _ = self.planner.check_battery_safety(
            (1, 4), current_battery=20, stations={(1, 0)}, known_obstacles=obstacles
        )
        self.assertFalse(is_crit)

    def test_agent_retreats_when_battery_critical(self):
        # Agent at (1, 3) with only 12 battery (return cost to (1, 0) is 6 + margin 6 = 12)
        obs = Observation(
            position=(1, 3),
            battery=12,
            time_tick=5,
            at_recharge_station=False,
            visible_tiles={(1, 3): "."}
        )
        decision = self.agent.decide_action(obs)
        self.assertEqual(decision.mode, "RETREAT_TO_RECHARGE")
        # Next move should head North towards (1, 0)
        self.assertEqual(decision.action, ActionType.MOVE_N)

    def test_agent_recharges_at_station(self):
        obs = Observation(
            position=(1, 0),
            battery=40,
            time_tick=10,
            at_recharge_station=True,
            visible_tiles={(1, 0): "R"}
        )
        decision = self.agent.decide_action(obs)
        self.assertEqual(decision.action, ActionType.RECHARGE)
        self.assertEqual(decision.mode, "RECHARGING")

    def test_agent_inspects_nearby_clue(self):
        obs = Observation(
            position=(1, 1),
            battery=80,
            time_tick=2,
            nearby_clue_available=True,
            visible_tiles={(2, 1): "?"}
        )
        decision = self.agent.decide_action(obs)
        self.assertEqual(decision.action, ActionType.INSPECT)
        self.assertEqual(decision.mode, "INSPECTING_CLUE")

    def test_agent_visual_contact_rescues_eve(self):
        # WALL-E at (8, 9), sees EVE at (8, 8) within 10x10 grid bounds
        obs = Observation(
            position=(8, 9),
            battery=60,
            time_tick=20,
            visible_tiles={(8, 8): "E", (8, 9): "."}
        )
        decision = self.agent.decide_action(obs)
        self.assertEqual(decision.action, ActionType.MOVE_N)
        self.assertEqual(decision.mode, "RESCUING")
        self.assertEqual(decision.target_coord, (8, 8))
        self.assertEqual(self.agent.belief.grid[(8, 8)], 1.0)
        self.assertEqual(self.agent.latest_summary.best_estimate, (8, 8))


if __name__ == "__main__":
    unittest.main()
