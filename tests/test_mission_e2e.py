"""End-to-end simulation tests for WALL-E missions."""

import os
import unittest
from walle.agent import AutonomousWallEAgent
from walle.config import MissionConfig
from walle.environment import MissionStatus, WallEEnvironment
from walle.logger import MissionLogger
from walle.report import MissionReportGenerator


class TestMissionE2E(unittest.TestCase):

    def test_run_mission_01_basic(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "configs", "mission_01_basic.json")
        config = MissionConfig.load(config_path)

        env = WallEEnvironment(config, seed=config.seed)
        agent = AutonomousWallEAgent(config)
        logger = MissionLogger(config.name, verbose=False)

        obs = env.reset()
        step = 0
        max_steps = 100

        while obs.mission_status == MissionStatus.IN_PROGRESS and step < max_steps:
            step += 1
            obs_before = obs
            decision = agent.decide_action(obs_before)
            obs_after, meta = env.step(decision.action)
            summary = agent.latest_summary

            logger.log_step(step, obs_before, decision, obs_after, meta, summary)
            obs = obs_after

        # Assertions
        self.assertGreater(step, 0)
        self.assertIn(obs.mission_status, [MissionStatus.SUCCESS_FOUND_EVE, MissionStatus.IN_PROGRESS])

        # Generate report
        report_gen = MissionReportGenerator(
            config=config,
            traces=logger.traces,
            final_summary=agent.latest_summary,
            mission_status=obs.mission_status,
            ground_truth=env.get_ground_truth_for_eval()
        )
        md = report_gen.generate_markdown()
        self.assertIn("WALL-E Mission Report", md)
        self.assertIn("Recommended Next Move", md)
        self.assertIn("Evidence Dossier", md)

    def test_run_mission_03_resource_scarce(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "configs", "mission_03_resource_scarce.json")
        config = MissionConfig.load(config_path)

        env = WallEEnvironment(config, seed=config.seed)
        agent = AutonomousWallEAgent(config)
        logger = MissionLogger(config.name, verbose=False)

        obs = env.reset()
        step = 0
        max_steps = 120

        while obs.mission_status == MissionStatus.IN_PROGRESS and step < max_steps:
            step += 1
            obs_before = obs
            decision = agent.decide_action(obs_before)
            obs_after, meta = env.step(decision.action)
            summary = agent.latest_summary

            logger.log_step(step, obs_before, decision, obs_after, meta, summary)
            obs = obs_after

        # Verify that battery never dips below zero
        for t in logger.traces:
            self.assertGreaterEqual(t.battery_after, 0)

        # Agent should have conducted at least 1 recharge
        recharges = [t for t in logger.traces if t.action == "RECHARGE"]
        self.assertGreater(len(recharges), 0)


if __name__ == "__main__":
    unittest.main()
