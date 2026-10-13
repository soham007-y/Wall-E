"""Mission report generator for WALL-E and EVE exploration."""

from __future__ import annotations
import json
import math
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from walle.belief import BeliefSummary
from walle.config import MissionConfig
from walle.environment import MissionStatus
from walle.logger import StepTrace


@dataclass
class MissionMetrics:
    """Quantitative performance metrics."""
    outcome: str
    total_steps: int
    time_ticks: int
    initial_battery: int
    final_battery: int
    battery_consumed: int
    recharge_events: int
    total_distance_traveled: float
    clues_found: int
    initial_entropy: float
    final_entropy: float
    entropy_reduction_pct: float
    best_estimate: Tuple[int, int]
    best_estimate_confidence_pct: float
    credible_radius: float
    inferred_status: str
    localization_error_euclidean: Optional[float] = None


class MissionReportGenerator:
    """Generates detailed Markdown and JSON mission reports."""

    def __init__(
        self,
        config: MissionConfig,
        traces: List[StepTrace],
        final_summary: BeliefSummary,
        mission_status: MissionStatus,
        ground_truth: Optional[Dict[str, Any]] = None,
    ):
        self.config = config
        self.traces = traces
        self.final_summary = final_summary
        self.mission_status = mission_status
        self.ground_truth = ground_truth
        self.metrics = self._calculate_metrics()

    def _calculate_metrics(self) -> MissionMetrics:
        """Compute summary metrics from execution traces."""
        total_steps = len(self.traces)
        final_time = self.traces[-1].time_tick if self.traces else 0
        init_bat = self.config.resources.initial_battery
        final_bat = self.traces[-1].battery_after if self.traces else init_bat

        # Calculate total distance traveled
        dist = 0.0
        for i in range(1, len(self.traces)):
            p1 = self.traces[i - 1].position
            p2 = self.traces[i].position
            dist += math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

        # Count recharges and clues
        recharges = sum(1 for t in self.traces if t.action == "RECHARGE")
        clues_found = sum(1 for t in self.traces if t.inspected_clue is not None)

        init_entropy = self.traces[0].belief_entropy if self.traces else 0.0
        final_entropy = self.final_summary.entropy
        entropy_reduction = 0.0
        if init_entropy > 0:
            entropy_reduction = max(0.0, (init_entropy - final_entropy) / init_entropy * 100.0)

        loc_error = None
        if self.ground_truth and "eve_true_position" in self.ground_truth:
            true_pos = self.ground_truth["eve_true_position"]
            best_pos = self.final_summary.best_estimate
            loc_error = math.sqrt((true_pos[0] - best_pos[0]) ** 2 + (true_pos[1] - best_pos[1]) ** 2)

        return MissionMetrics(
            outcome=self.mission_status.value,
            total_steps=total_steps,
            time_ticks=final_time,
            initial_battery=init_bat,
            final_battery=final_bat,
            battery_consumed=max(0, init_bat - final_bat + recharges * self.config.resources.recharge_rate),
            recharge_events=recharges,
            total_distance_traveled=round(dist, 2),
            clues_found=clues_found,
            initial_entropy=round(init_entropy, 3),
            final_entropy=round(final_entropy, 3),
            entropy_reduction_pct=round(entropy_reduction, 1),
            best_estimate=self.final_summary.best_estimate,
            best_estimate_confidence_pct=round(self.final_summary.max_prob * 100.0, 2),
            credible_radius=round(self.final_summary.credible_radius, 2),
            inferred_status=self.final_summary.inferred_status,
            localization_error_euclidean=round(loc_error, 2) if loc_error is not None else None,
        )

    def generate_recommended_next_step(self) -> str:
        """Formulate actionable tactical protocol for WALL-E."""
        est_x, est_y = self.final_summary.best_estimate
        status = self.final_summary.inferred_status

        if self.mission_status == MissionStatus.SUCCESS_FOUND_EVE:
            if status == "DORMANT_REBOOT_REQUIRED":
                return (
                    f"Initiate physical interface protocol at coordinates ({est_x}, {est_y}). "
                    f"Connect auxiliary solar jumper cable and broadcast reboot authorization code 2105-A."
                )
            elif status == "DAMAGED_THRUSTER":
                return (
                    f"Deploy mechanical support clamps at ({est_x}, {est_y}). "
                    f"Stabilize EVE's propulsion housing and initiate low-speed towing to repair shelter."
                )
            else:
                return f"Establish primary handshake telemetry link at coordinates ({est_x}, {est_y}) and initiate diagnostics."

        elif self.mission_status == MissionStatus.FAILED_BATTERY_DEPLETED:
            return (
                f"WALL-E battery depleted at position {self.traces[-1].position if self.traces else 'unknown'}. "
                f"Emergency protocol: Deploy solar collector hood and wait for daylight replenishment."
            )
        else:
            return (
                f"Advance scout drones to coordinates ({est_x}, {est_y}) within 90% confidence radius of "
                f"{self.final_summary.credible_radius:.1f} tiles to confirm EVE visual contact."
            )

    def generate_markdown(self) -> str:
        """Render complete Markdown mission report."""
        m = self.metrics
        status_badge = "✅ **MISSION SUCCESS**" if "SUCCESS" in m.outcome else "❌ **MISSION FAILED**"

        # Evidence table
        evidence_rows = []
        for t in self.traces:
            if t.inspected_clue:
                c = t.inspected_clue
                evidence_rows.append(
                    f"| Step {t.step_number} | ({c.get('x')}, {c.get('y')}) | `{c.get('type')}` | {c.get('description')} |"
                )
        evidence_table = "\n".join(evidence_rows) if evidence_rows else "| - | - | - | No clues gathered |"

        rec_next_step = self.generate_recommended_next_step()

        ground_truth_section = ""
        if m.localization_error_euclidean is not None:
            gt_pos = self.ground_truth['eve_true_position']  # type: ignore
            ground_truth_section = f"""
### Ground Truth Verification (Eval Mode)
- **True EVE Location**: `({gt_pos[0]}, {gt_pos[1]})`
- **True EVE Status**: `{self.ground_truth.get('eve_status')}`
- **Localization Error**: `{m.localization_error_euclidean:.2f} tiles` ({'Exact Match!' if m.localization_error_euclidean == 0 else 'Close proximity'})
"""

        md = f"""# 🤖 WALL-E Mission Report: Locating EVE's Signal

**Mission**: {self.config.name}  
**Status**: {status_badge} (`{m.outcome}`)  
**Simulation Ticks**: {m.time_ticks} | **Execution Steps**: {m.total_steps}  

---

## 📊 Executive Summary & Key Metrics

| Metric | Result | Description |
| :--- | :--- | :--- |
| **Inferred EVE Coordinates** | `({m.best_estimate[0]}, {m.best_estimate[1]})` | Peak posterior coordinate from Bayesian spatial map |
| **Peak Posterior Confidence** | **{m.best_estimate_confidence_pct}%** | Posterior certainty at candidate coordinate |
| **Credible Radius (90%)** | `{m.credible_radius} tiles` | Radius encompassing 90% of probability distribution |
| **Inferred Operational State** | `{m.inferred_status}` | Diagnosed from gathered telemetry clues |
| **Entropy Reduction** | **{m.entropy_reduction_pct}%** | Information gain: `{m.initial_entropy:.2f}` $\\to$ `{m.final_entropy:.2f}` bits |
| **Battery Consumed** | `{m.battery_consumed}%` (Final: `{m.final_battery}%`) | Total energy expenditure across mission |
| **Solar Recharge Events** | `{m.recharge_events}` | Strategic recharging stops at solar stations |
| **Distance Traveled** | `{m.total_distance_traveled} units` | Total path distance across terrain |
| **Clues Discovered** | `{m.clues_found}` | Environmental and telemetry clue signatures |

{ground_truth_section}

---

## 🔍 Evidence Dossier

The autonomous agent gathered and interpreted the following clues through interaction:

| Step | Location | Type | Deciphered Evidence |
| :--- | :---: | :--- | :--- |
{evidence_table}

---

## 🚀 WALL-E's Recommended Next Move

> **Tactical Directive:**  
> {rec_next_step}

---

## 🧭 Spatial Candidate Distribution (Top 3)

"""
        for i, (cand, prob) in enumerate(self.final_summary.top_candidates[:3], 1):
            md += f"{i}. Coordinate `({cand[0]}, {cand[1]})` — Posterior Probability: **{prob * 100:.2f}%**\n"

        md += "\n---\n*Report generated autonomously by WALL-E Mission Assessment Subsystem.*"
        return md

    def save_reports(self, md_path: str, json_path: Optional[str] = None):
        """Save report to Markdown and JSON files."""
        os.makedirs(os.path.dirname(os.path.abspath(md_path)), exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown())

        if json_path:
            os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
            report_dict = {
                "mission_name": self.config.name,
                "metrics": asdict(self.metrics),
                "recommended_next_step": self.generate_recommended_next_step(),
                "top_candidates": [
                    {"coord": list(c), "prob": round(p, 4)}
                    for c, p in self.final_summary.top_candidates
                ],
                "ground_truth": self.ground_truth,
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(report_dict, f, indent=2)
