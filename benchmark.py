#!/usr/bin/env python3
"""Generalization benchmark suite testing WALL-E across randomized procedural missions."""

import argparse
import random
from typing import List

from walle.agent import AutonomousWallEAgent
from walle.config import ClueData, MapConfig, MissionConfig, ResourceConfig, SensorConfig
from walle.environment import MissionStatus, WallEEnvironment
from walle.logger import MissionLogger
from walle.report import MissionMetrics, MissionReportGenerator


def create_procedural_mission(seed: int, width: int = 16, height: int = 16) -> MissionConfig:
    """Generate a valid procedural mission with obstacles, recharge stations, clues, and EVE."""
    rng = random.Random(seed)

    walle_start = (1, 1)
    eve_pos = (rng.randint(width // 2, width - 2), rng.randint(height // 2, height - 2))

    # Generate 15-25 obstacles ensuring start and goal are free
    obstacles = []
    num_obstacles = rng.randint(15, 25)
    for _ in range(num_obstacles):
        ox = rng.randint(0, width - 1)
        oy = rng.randint(0, height - 1)
        if (ox, oy) not in [walle_start, eve_pos] and (ox, oy) not in obstacles:
            obstacles.append((ox, oy))

    # Recharge stations
    recharge_stations = [
        (rng.randint(2, width // 2), rng.randint(2, height // 2)),
        (rng.randint(width // 2, width - 2), rng.randint(2, height // 2)),
    ]

    # Clues
    clues = [
        ClueData(
            id=f"seed_{seed}_clue_heading",
            x=rng.randint(2, width - 3),
            y=rng.randint(2, height - 3),
            description="Heading indicator to target sector.",
            clue_type="heading",
            payload={"bearing_range": [0, 180]},
        ),
        ClueData(
            id=f"seed_{seed}_clue_status",
            x=rng.randint(2, width - 3),
            y=rng.randint(2, height - 3),
            description="Status beacon telemetry log.",
            clue_type="status_telemetry",
            payload={"status": "DORMANT_REBOOT_REQUIRED"},
        ),
    ]

    map_cfg = MapConfig(
        width=width,
        height=height,
        walle_start=walle_start,
        eve_position=eve_pos,
        eve_status="DORMANT_REBOOT_REQUIRED",
        obstacles=obstacles,
        recharge_stations=recharge_stations,
        clues=clues,
    )

    return MissionConfig(
        name=f"Procedural Benchmark Seed {seed}",
        description="Benchmarking generalization over randomized terrain and signal conditions.",
        map_config=map_cfg,
        resources=ResourceConfig(
            initial_battery=100,
            max_battery=100,
            max_time_ticks=150,
            move_cost=2,
            scan_cost=4,
            inspect_cost=3,
            recharge_rate=20,
            safety_margin=6,
        ),
        sensor=SensorConfig(
            p0=-20.0,
            eta=2.0,
            rssi_noise_std=1.2,
            bearing_noise_std_deg=8.0,
            obstacle_attenuation_db=3.5,
        ),
        seed=seed,
    )


def run_benchmark(num_missions: int = 10, start_seed: int = 100):
    print("=" * 70)
    print(f"🔬 RUNNING GENERALIZATION BENCHMARK ACROSS {num_missions} PROCEDURAL MISSIONS")
    print("=" * 70)

    results: List[MissionMetrics] = []

    for i in range(num_missions):
        seed = start_seed + i * 17
        cfg = create_procedural_mission(seed)

        env = WallEEnvironment(cfg, seed=seed)
        agent = AutonomousWallEAgent(cfg)
        logger = MissionLogger(cfg.name, verbose=False)

        obs = env.reset()
        step = 0
        while obs.mission_status == MissionStatus.IN_PROGRESS and step < cfg.resources.max_time_ticks:
            step += 1
            obs_before = obs
            decision = agent.decide_action(obs_before)
            obs_after, meta = env.step(decision.action)
            summary = agent.latest_summary
            logger.log_step(step, obs_before, decision, obs_after, meta, summary)
            obs = obs_after

        report_gen = MissionReportGenerator(
            config=cfg,
            traces=logger.traces,
            final_summary=agent.latest_summary,
            mission_status=obs.mission_status,
            ground_truth=env.get_ground_truth_for_eval(),
        )
        m = report_gen.metrics
        results.append(m)

        status_emoji = "✅" if "SUCCESS" in m.outcome else "❌"
        err_str = f"{m.localization_error_euclidean:.1f} tiles" if m.localization_error_euclidean is not None else "N/A"
        print(f"Mission #{i+1:02d} (Seed {seed}) | {status_emoji} {m.outcome:<18} | Steps: {m.total_steps:02d} | "
              f"Bat: {m.final_battery:>3}% | Error: {err_str:<9} | Entropy Red: {m.entropy_reduction_pct:.1f}%")

    # Aggregate Statistics
    successes = sum(1 for m in results if "SUCCESS" in m.outcome)
    success_rate = (successes / num_missions) * 100.0
    avg_steps = sum(m.total_steps for m in results) / num_missions
    avg_battery = sum(m.final_battery for m in results) / num_missions
    avg_entropy_red = sum(m.entropy_reduction_pct for m in results) / num_missions
    loc_errors = [m.localization_error_euclidean for m in results if m.localization_error_euclidean is not None]
    avg_loc_error = sum(loc_errors) / len(loc_errors) if loc_errors else 0.0

    print("\n" + "=" * 70)
    print("📊 BENCHMARK SUMMARY REPORT")
    print("=" * 70)
    print(f"Total Missions Evaluated  : {num_missions}")
    print(f"Mission Success Rate      : {success_rate:.1f}% ({successes}/{num_missions})")
    print(f"Average Execution Steps   : {avg_steps:.1f} steps")
    print(f"Average Final Battery     : {avg_battery:.1f}%")
    print(f"Average Localization Error: {avg_loc_error:.2f} tiles")
    print(f"Average Entropy Reduction : {avg_entropy_red:.1f}%")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="WALL-E Benchmark Runner")
    parser.add_argument("--num-missions", type=int, default=10, help="Number of missions to benchmark")
    parser.add_argument("--start-seed", type=int, default=100, help="Starting random seed")
    args = parser.parse_args()
    run_benchmark(num_missions=args.num_missions, start_seed=args.start_seed)


if __name__ == "__main__":
    main()
