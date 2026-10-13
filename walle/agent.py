"""Autonomous WALL-E agent with Bayesian perception, resource-safe budgeting, and goal arbitration."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from walle.belief import BayesianBeliefMap, BeliefSummary
from walle.config import MissionConfig
from walle.environment import ActionType, DIRECTION_OFFSETS, MissionStatus, Observation
from walle.planner import GridPlanner


@dataclass
class AgentDecision:
    """Agent action decision accompanied by its rationale."""
    action: ActionType
    reasoning: str
    mode: str
    target_coord: Optional[Tuple[int, int]] = None


class AutonomousWallEAgent:
    """Autonomous agent that explores, manages battery, updates Bayesian beliefs, and locates EVE."""

    def __init__(self, config: MissionConfig):
        self.config = config
        self.width = config.map_config.width
        self.height = config.map_config.height

        # Belief engine
        self.belief = BayesianBeliefMap(config)

        # Path planner
        self.planner = GridPlanner(self.width, self.height, config.resources)

        # Agent memory & knowledge base (built strictly through interaction)
        self.known_obstacles: Set[Tuple[int, int]] = set()
        # Recharge stations provided in mission briefing or discovered
        self.known_recharge_stations: Set[Tuple[int, int]] = set(config.map_config.recharge_stations)
        self.visited_tiles: Set[Tuple[int, int]] = set()
        self.discovered_clue_ids: Set[str] = set()

        # Exploration tracking
        self.steps_since_last_scan: int = 0
        self.current_mode: str = "EXPLORATION"
        self.last_scanned_pos: Optional[Tuple[int, int]] = None
        self.latest_summary: BeliefSummary = self.belief.get_summary()

    def decide_action(self, obs: Observation) -> AgentDecision:
        """Process observation, update belief, and decide next action with explicit reasoning."""
        self.visited_tiles.add(obs.position)

        # 1. Update internal map with visible tiles
        for tile_coord, tile_type in obs.visible_tiles.items():
            if tile_type == "#":
                self.known_obstacles.add(tile_coord)
                self.belief.mark_obstacle(tile_coord)
            elif tile_type == "R":
                self.known_recharge_stations.add(tile_coord)

        # 2. Update Bayesian belief with sensor reading
        # If WALL-E is on this cell and EVE was not found, this cell cannot be EVE
        if obs.position in self.belief.grid and obs.mission_status != MissionStatus.SUCCESS_FOUND_EVE:
            self.belief.grid[obs.position] = 0.0
            self.belief._normalize()

        if obs.rssi is not None and obs.position != self.last_scanned_pos:
            self.belief.update_sensor_measurement(obs.position, obs.rssi, obs.bearing_deg)
            self.last_scanned_pos = obs.position

        # 3. Process inspected clue if just gathered
        if obs.inspected_clue is not None:
            clue_id = obs.inspected_clue.get("id")
            if clue_id and clue_id not in self.discovered_clue_ids:
                self.discovered_clue_ids.add(clue_id)
                self.belief.update_clue(obs.position, obs.inspected_clue)

        self.latest_summary = self.belief.get_summary()
        summary = self.latest_summary

        # 4. Check if currently at a recharge station
        if obs.at_recharge_station:
            battery_pct = obs.battery / self.config.resources.max_battery
            if battery_pct < 0.90:
                self.current_mode = "RECHARGING"
                return AgentDecision(
                    action=ActionType.RECHARGE,
                    reasoning=f"Solar recharging active. Battery at {obs.battery}% ({battery_pct*100:.0f}% capacity). Restoring energy reserves.",
                    mode="RECHARGING",
                    target_coord=obs.position,
                )

        # 5. Check Battery Safety Margin (Point of No Return)
        is_critical, return_cost, nearest_station = self.planner.check_battery_safety(
            obs.position,
            obs.battery,
            self.known_recharge_stations,
            self.known_obstacles,
        )

        if is_critical and nearest_station is not None:
            self.current_mode = "RETREAT_TO_RECHARGE"
            path_res = self.planner.astar(obs.position, nearest_station, self.known_obstacles)
            if path_res.found and len(path_res.path) > 1:
                next_step = path_res.path[1]
                action = self._step_to_action(obs.position, next_step)
                return AgentDecision(
                    action=action,
                    reasoning=(
                        f"BATTERY CRITICAL: Battery at {obs.battery}%, return cost to station at {nearest_station} is {return_cost}. "
                        f"Safety threshold breached. Executing retreat protocol to recharge."
                    ),
                    mode="RETREAT_TO_RECHARGE",
                    target_coord=nearest_station,
                )

        # 6. Clue Inspection: If uninspected clue is immediately adjacent, INSPECT it!
        if obs.nearby_clue_available:
            self.current_mode = "INSPECTING_CLUE"
            return AgentDecision(
                action=ActionType.INSPECT,
                reasoning="Proximity radar detected physical clue or telemetry beacon signature. Deciphering clue payload.",
                mode="INSPECTING_CLUE",
                target_coord=obs.position,
            )

        # 7. Triangulation Scan: If agent moved sufficiently far or needs fresh reading
        if self.steps_since_last_scan >= 4 and obs.battery >= 25 and summary.entropy > 2.5:
            self.steps_since_last_scan = 0
            self.last_scanned_pos = obs.position
            self.current_mode = "TRIANGULATING"
            return AgentDecision(
                action=ActionType.SCAN,
                reasoning=(
                    f"Belief entropy is {summary.entropy:.2f} bits. Dispatched directional radar ping "
                    f"to triangulate EVE's signal from current position {obs.position}."
                ),
                mode="TRIANGULATING",
                target_coord=obs.position,
            )

        # 8. Target Arbitration & Navigation
        best_coord = summary.best_estimate
        self.current_mode = "CONVERGING" if summary.max_prob > 0.30 else "EXPLORING"

        # If already at peak candidate or immediately adjacent
        if obs.position == best_coord:
            # At target! If EVE is here, action will confirm, else scan
            if self.steps_since_last_scan > 0:
                self.steps_since_last_scan = 0
                return AgentDecision(
                    action=ActionType.SCAN,
                    reasoning=f"Arrived at peak candidate {best_coord}. Scanning to confirm EVE beacon signature.",
                    mode="CONFIRMING",
                    target_coord=best_coord,
                )

        # Plan path to best candidate
        target_dest = self._select_exploration_target(obs.position, summary)
        path_res = self.planner.astar(obs.position, target_dest, self.known_obstacles)

        if path_res.found and len(path_res.path) > 1:
            next_step = path_res.path[1]
            action = self._step_to_action(obs.position, next_step)
            self.steps_since_last_scan += 1
            return AgentDecision(
                action=action,
                reasoning=(
                    f"Navigating toward high-likelihood target {target_dest} (peak {summary.max_prob*100:.1f}%, entropy {summary.entropy:.2f}). "
                    f"Next waypoint: {next_step}."
                ),
                mode=self.current_mode,
                target_coord=target_dest,
            )

        # Fallback: scan if no path found
        self.steps_since_last_scan = 0
        return AgentDecision(
            action=ActionType.SCAN,
            reasoning="Path blocked or target reached; initiating deep scan to refresh belief distribution.",
            mode="SCANNING",
            target_coord=obs.position,
        )

    def _select_exploration_target(
        self,
        current_pos: Tuple[int, int],
        summary: BeliefSummary
    ) -> Tuple[int, int]:
        """Select best destination balancing posterior probability and path distance."""
        best_target = summary.best_estimate
        best_score = -999999.0

        # Sort all non-obstacle cells by probability
        candidates = [c for c in summary.top_candidates if c[0] not in self.known_obstacles and c[0] != current_pos]
        if not candidates:
            # Fallback to any unvisited cell with non-zero probability
            candidates = sorted(
                [(coord, prob) for coord, prob in self.belief.grid.items() if coord not in self.known_obstacles and coord != current_pos],
                key=lambda x: x[1],
                reverse=True
            )[:10]

        for (cand, prob) in candidates:
            dist = abs(cand[0] - current_pos[0]) + abs(cand[1] - current_pos[1])
            # Bonus for unvisited tiles, penalty for already visited
            visit_penalty = 50.0 if cand in self.visited_tiles else 0.0
            score = prob * 100.0 - dist * 0.5 - visit_penalty
            if score > best_score:
                best_score = score
                best_target = cand

        return best_target

    def _step_to_action(self, current: Tuple[int, int], next_pos: Tuple[int, int]) -> ActionType:
        """Convert consecutive grid coordinates into a movement ActionType."""
        dx = next_pos[0] - current[0]
        dy = next_pos[1] - current[1]
        for action, offset in DIRECTION_OFFSETS.items():
            if offset == (dx, dy):
                return action
        return ActionType.WAIT
