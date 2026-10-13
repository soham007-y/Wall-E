"""Unit tests for BayesianBeliefMap."""

import math
import unittest
from walle.config import MapConfig, MissionConfig, ResourceConfig, SensorConfig
from walle.belief import BayesianBeliefMap


class TestBayesianBelief(unittest.TestCase):

    def setUp(self):
        self.map_config = MapConfig(
            width=10,
            height=10,
            walle_start=(0, 0),
            eve_position=(7, 7),
            eve_status="DORMANT_REBOOT_REQUIRED",
        )
        self.config = MissionConfig(
            name="Belief Test",
            description="Testing belief map",
            map_config=self.map_config,
            sensor=SensorConfig(
                p0=-20.0,
                eta=2.0,
                rssi_noise_std=1.0,
                bearing_noise_std_deg=5.0
            )
        )
        self.belief = BayesianBeliefMap(self.config)

    def test_initial_uniform_prior(self):
        # 10x10 = 100 cells. Each cell has p = 0.01
        self.assertEqual(len(self.belief.grid), 100)
        self.assertAlmostEqual(sum(self.belief.grid.values()), 1.0, places=5)
        expected_entropy = math.log2(100)
        self.assertAlmostEqual(self.belief.compute_entropy(), expected_entropy, places=3)

    def test_sensor_update_focuses_probability(self):
        initial_entropy = self.belief.compute_entropy()

        # True distance from (0,0) to (7,7) is sqrt(98) ~ 9.899
        dist = math.sqrt(98)
        rssi = -20.0 - 20.0 * math.log10(dist)
        bearing = 45.0  # Exactly towards (7, 7)

        self.belief.update_sensor_measurement((0, 0), rssi, bearing)

        # Entropy must decrease after measurement
        new_entropy = self.belief.compute_entropy()
        self.assertLess(new_entropy, initial_entropy)

        # The peak candidate should be near (7, 7)
        summary = self.belief.get_summary()
        peak_x, peak_y = summary.best_estimate
        self.assertTrue(abs(peak_x - 7) <= 1 and abs(peak_y - 7) <= 1)

    def test_clue_sector_elimination(self):
        # Eliminate western half: x in [0, 4]
        clue = {
            "type": "sector_elimination",
            "payload": {"x_min": 0, "x_max": 4, "y_min": 0, "y_max": 9}
        }
        self.belief.update_clue((0, 0), clue)

        # Verify eliminated cells have 0 probability
        for y in range(10):
            for x in range(5):
                self.assertEqual(self.belief.grid[(x, y)], 0.0)

        # Total probability is still 1.0
        self.assertAlmostEqual(sum(self.belief.grid.values()), 1.0, places=5)

    def test_clue_status_telemetry(self):
        clue = {
            "type": "status_telemetry",
            "payload": {"status": "DAMAGED_THRUSTER"}
        }
        self.belief.update_clue((0, 0), clue)

        summary = self.belief.get_summary()
        self.assertEqual(summary.inferred_status, "DAMAGED_THRUSTER")
        self.assertGreater(summary.status_confidence, 0.90)


if __name__ == "__main__":
    unittest.main()
