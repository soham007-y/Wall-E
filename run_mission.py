#!/usr/bin/env python3
"""Main CLI entry point to execute WALL-E exploration missions."""

import argparse
import os
import sys
import time

from walle.agent import AutonomousWallEAgent
from walle.config import MissionConfig
from walle.environment import MissionStatus, WallEEnvironment
from walle.logger import MissionLogger
from walle.report import MissionReportGenerator
from walle.visualizer_ascii import AsciiVisualizer
from walle.visualizer_html import HtmlVisualizerGenerator
from walle.visualizer_3d import ThreeJsVisualizerGenerator


def run_mission(
    config_path: str,
    visualize: bool = False,
    replay: bool = False,
    generate_html: bool = True,
    generate_3d: bool = True,
    verbose: bool = False,
    output_dir: str = "traces",
    seed: int = None,
):
    print(f"Loading mission configuration from: {config_path}")
    config = MissionConfig.load(config_path)
    if seed is not None:
        config.seed = seed

    env = WallEEnvironment(config, seed=config.seed)
    agent = AutonomousWallEAgent(config)
    logger = MissionLogger(config.name, verbose=verbose)
    ascii_vis = AsciiVisualizer(config) if (visualize or replay) else None

    # Storage for 2D probability matrices for HTML scrubbing
    prob_history = []

    obs = env.reset()
    step = 0
    max_steps = config.resources.max_time_ticks

    print(f"\n🚀 Initiating Mission: {config.name}")
    print(f"🗺️  Map Size: {config.map_config.width}x{config.map_config.height} | Battery: {config.resources.initial_battery}%")
    print(f"🎯 Target Status: {config.map_config.eve_status}")
    print("-" * 60)

    # Record initial step 0 state
    prob_history.append(agent.belief.get_probability_matrix())

    while obs.mission_status == MissionStatus.IN_PROGRESS and step < max_steps:
        step += 1
        obs_before = obs

        # Agent decides action
        decision = agent.decide_action(obs_before)

        # Environment processes physics
        obs_after, meta = env.step(decision.action)

        # Summary snapshot
        summary = agent.latest_summary
        trace = logger.log_step(step, obs_before, decision, obs_after, meta, summary)
        prob_history.append(agent.belief.get_probability_matrix())

        if visualize and ascii_vis:
            ascii_vis.render_step(trace, clear_screen=True)
            time.sleep(0.08)

        obs = obs_after

    print("\n" + "=" * 60)
    print(f"🏁 Mission Concluded: {obs.mission_status.value}")
    print(f"📈 Total Steps: {step} | Final Battery: {obs.battery}% | Discovered Clues: {len(agent.discovered_clue_ids)}")
    print("=" * 60)

    # Generate Reports
    gt = env.get_ground_truth_for_eval()
    report_gen = MissionReportGenerator(
        config=config,
        traces=logger.traces,
        final_summary=agent.latest_summary,
        mission_status=obs.mission_status,
        ground_truth=gt,
    )

    base_name = os.path.splitext(os.path.basename(config_path))[0]
    os.makedirs(output_dir, exist_ok=True)

    # Save traces
    json_trace_path = os.path.join(output_dir, f"{base_name}_trace.json")
    jsonl_trace_path = os.path.join(output_dir, f"{base_name}_trace.jsonl")
    logger.save_traces(json_trace_path, jsonl_trace_path)
    print(f"📁 Traces saved to: {json_trace_path}")

    # Save reports
    md_report_path = os.path.join(output_dir, f"{base_name}_report.md")
    json_report_path = os.path.join(output_dir, f"{base_name}_report.json")
    report_gen.save_reports(md_report_path, json_report_path)
    print(f"📄 Report saved to: {md_report_path}")

    # Generate HTML Dashboard
    if generate_html:
        html_path = os.path.join(output_dir, f"{base_name}_dashboard.html")
        HtmlVisualizerGenerator.save_dashboard(
            output_path=html_path,
            config=config,
            traces=logger.traces,
            metrics=report_gen.metrics,
            report_markdown=report_gen.generate_markdown(),
            probability_history=prob_history,
            ground_truth=gt,
        )
        print(f"🌐 Interactive Visualizer saved to: {html_path}")
        # Also copy as root visualizer.html for easy access
        root_html = os.path.join(os.path.dirname(__file__), "visualizer.html")
        HtmlVisualizerGenerator.save_dashboard(
            output_path=root_html,
            config=config,
            traces=logger.traces,
            metrics=report_gen.metrics,
            report_markdown=report_gen.generate_markdown(),
            probability_history=prob_history,
            ground_truth=gt,
        )
        print(f"🌐 Root Visualizer saved to: {root_html}")

    # Generate 3D WebGL Dashboard
    if generate_3d:
        three_d_path = os.path.join(os.path.dirname(__file__), "visualizer_3d.html")
        all_configs = [
            "configs/mission_01_basic.json",
            "configs/mission_02_debris_field.json",
            "configs/mission_03_resource_scarce.json",
            "configs/mission_04_decoy_signals.json"
        ]
        ThreeJsVisualizerGenerator.build_and_save(all_configs, three_d_path)

    # Replay if requested
    if replay and ascii_vis:
        print("\nStarting terminal replay...")
        time.sleep(1.0)
        ascii_vis.replay_traces(logger.traces, delay=0.12)

    return report_gen.metrics


def main():
    parser = argparse.ArgumentParser(description="WALL-E Autonomous Mission Simulator")
    parser.add_argument("--config", default="configs/mission_01_basic.json", help="Path to mission config JSON")
    parser.add_argument("--visualize", action="store_true", help="Live terminal ASCII visualization")
    parser.add_argument("--replay", action="store_true", help="Replay mission in terminal after completion")
    parser.add_argument("--no-html", action="store_true", help="Disable HTML dashboard generation")
    parser.add_argument("--no-3d", action="store_true", help="Disable 3D WebGL website generation")
    parser.add_argument("--verbose", action="store_true", help="Print verbose step trace to stdout")
    parser.add_argument("--output-dir", default="traces", help="Directory for output files")
    parser.add_argument("--seed", type=int, default=None, help="Random seed override")

    args = parser.parse_args()
    run_mission(
        config_path=args.config,
        visualize=args.visualize,
        replay=args.replay,
        generate_html=not args.no_html,
        generate_3d=not args.no_3d,
        verbose=args.verbose,
        output_dir=args.output_dir,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
