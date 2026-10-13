"""Action tracing and structured logging for WALL-E mission executions."""

from __future__ import annotations
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from walle.agent import AgentDecision
from walle.belief import BeliefSummary
from walle.environment import Observation


@dataclass
class StepTrace:
    """Complete trace record of a single simulation step."""
    step_number: int
    time_tick: int
    action: str
    action_cost: int
    battery_before: int
    battery_after: int
    position: Tuple[int, int]
    observation_rssi: Optional[float]
    observation_bearing_deg: Optional[float]
    inspected_clue: Optional[Dict[str, Any]]
    agent_mode: str
    agent_reasoning: str
    target_coord: Optional[Tuple[int, int]]
    belief_entropy: float
    belief_peak_coord: Tuple[int, int]
    belief_peak_prob: float
    inferred_status: str
    status_message: str


class MissionLogger:
    """Collects step traces, prints formatted console logs, and exports to JSON/JSONL."""

    def __init__(self, mission_name: str, verbose: bool = False):
        self.mission_name = mission_name
        self.verbose = verbose
        self.traces: List[StepTrace] = []

    def log_step(
        self,
        step_number: int,
        obs_before: Observation,
        decision: AgentDecision,
        obs_after: Observation,
        step_meta: Dict[str, Any],
        summary: BeliefSummary,
    ) -> StepTrace:
        """Record and format a simulation step."""
        trace = StepTrace(
            step_number=step_number,
            time_tick=obs_after.time_tick,
            action=decision.action.value,
            action_cost=step_meta.get("cost", 0),
            battery_before=obs_before.battery,
            battery_after=obs_after.battery,
            position=obs_after.position,
            observation_rssi=round(obs_after.rssi, 2) if obs_after.rssi is not None else None,
            observation_bearing_deg=round(obs_after.bearing_deg, 1) if obs_after.bearing_deg is not None else None,
            inspected_clue=obs_after.inspected_clue,
            agent_mode=decision.mode,
            agent_reasoning=decision.reasoning,
            target_coord=decision.target_coord,
            belief_entropy=round(summary.entropy, 3),
            belief_peak_coord=summary.best_estimate,
            belief_peak_prob=round(summary.max_prob, 4),
            inferred_status=summary.inferred_status,
            status_message=obs_after.status_message,
        )
        self.traces.append(trace)

        if self.verbose:
            self._print_step(trace)

        return trace

    def _print_step(self, t: StepTrace):
        """Format a single step trace to console."""
        print(f"[{t.step_number:03d} | T:{t.time_tick:03d}] Act: {t.action:<8} | Pos: {t.position} | Bat: {t.battery_after:>3}% | "
              f"Peak: {t.belief_peak_coord} ({t.belief_peak_prob*100:4.1f}%) | H: {t.belief_entropy:.2f}")
        print(f"      Reason: {t.agent_reasoning}")
        if t.inspected_clue:
            print(f"      >>> CLUE: {t.inspected_clue.get('description')}")

    def save_traces(self, json_path: str, jsonl_path: Optional[str] = None):
        """Export collected traces to JSON and/or JSONL formats."""
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        raw_list = [asdict(t) for t in self.traces]

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "mission_name": self.mission_name,
                "total_steps": len(self.traces),
                "steps": raw_list
            }, f, indent=2)

        if jsonl_path:
            os.makedirs(os.path.dirname(os.path.abspath(jsonl_path)), exist_ok=True)
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for t in raw_list:
                    f.write(json.dumps(t) + "\n")
