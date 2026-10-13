"""Bayesian belief tracking engine for spatial localization and EVE status inference."""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from walle.config import MissionConfig, SensorConfig


@dataclass
class BeliefSummary:
    """Snapshot of current belief distribution state."""
    entropy: float
    max_prob: float
    best_estimate: Tuple[int, int]
    top_candidates: List[Tuple[Tuple[int, int], float]]
    inferred_status: str
    status_confidence: float
    credible_radius: float  # Radius containing 90% confidence


class BayesianBeliefMap:
    """Maintains 2D discrete probability distribution over EVE's coordinates and operational status."""

    def __init__(self, config: MissionConfig):
        self.width = config.map_config.width
        self.height = config.map_config.height
        self.sensor = config.sensor

        # 2D Probability grid: P(EVE at (x, y))
        self.grid: Dict[Tuple[int, int], float] = {}
        total_cells = self.width * self.height
        initial_p = 1.0 / total_cells

        for x in range(self.width):
            for y in range(self.height):
                self.grid[(x, y)] = initial_p

        # Known obstacles discovered during exploration
        self.known_obstacles: Set[Tuple[int, int]] = set()

        # Operational status belief distribution
        self.possible_statuses = [
            "DORMANT_REBOOT_REQUIRED",
            "DAMAGED_THRUSTER",
            "LOW_POWER_BEACON",
            "OPERATIONAL_TRANSMITTING",
        ]
        status_p = 1.0 / len(self.possible_statuses)
        self.status_belief: Dict[str, float] = {s: status_p for s in self.possible_statuses}

        # History of entropy values
        self.entropy_history: List[float] = [self.compute_entropy()]

    def mark_obstacle(self, pos: Tuple[int, int]):
        """Zero out probability for confirmed obstacle cells and renormalize."""
        if pos in self.grid and pos not in self.known_obstacles:
            self.known_obstacles.add(pos)
            self.grid[pos] = 0.0
            self._normalize()

    def update_sensor_measurement(
        self,
        wall_e_pos: Tuple[int, int],
        rssi: Optional[float],
        bearing_deg: Optional[float]
    ):
        """Update 2D spatial belief with RSSI signal and bearing angle."""
        if rssi is None and bearing_deg is None:
            return

        p0 = self.sensor.p0
        eta = self.sensor.eta
        rssi_sigma = max(self.sensor.rssi_noise_std, 0.5)
        bearing_sigma = max(self.sensor.bearing_noise_std_deg, 2.0)

        for (x, y), prior_p in self.grid.items():
            if prior_p <= 0.0:
                continue

            dx = x - wall_e_pos[0]
            dy = y - wall_e_pos[1]
            dist = math.sqrt(dx * dx + dy * dy)

            likelihood = 1.0

            # 1. RSSI Likelihood (Log-distance path loss)
            if rssi is not None:
                effective_dist = max(dist, 1.0)
                expected_rssi = p0 - 10.0 * eta * math.log10(effective_dist)
                rssi_diff = rssi - expected_rssi
                # Gaussian PDF factor
                rssi_l = math.exp(-0.5 * (rssi_diff / rssi_sigma) ** 2) / (math.sqrt(2 * math.pi) * rssi_sigma)
                likelihood *= max(rssi_l, 1e-12)

            # 2. Bearing Likelihood (Circular Gaussian / Von Mises approximation)
            if bearing_deg is not None and dist > 0.1:
                expected_bearing = math.degrees(math.atan2(dy, dx)) % 360.0
                bearing_diff = (bearing_deg - expected_bearing + 180.0) % 360.0 - 180.0
                bearing_l = math.exp(-0.5 * (bearing_diff / bearing_sigma) ** 2) / (math.sqrt(2 * math.pi) * bearing_sigma)
                likelihood *= max(bearing_l, 1e-12)

            self.grid[(x, y)] = prior_p * likelihood

        self._normalize()
        self.entropy_history.append(self.compute_entropy())

    def update_clue(self, wall_e_pos: Tuple[int, int], clue: Dict[str, Any]):
        """Condition belief map on qualitative or structural clue payload."""
        clue_type = clue.get("type", "general")
        payload = clue.get("payload", {})
        clue_x = clue.get("x", wall_e_pos[0])
        clue_y = clue.get("y", wall_e_pos[1])

        if clue_type == "distance_bound":
            min_d = float(payload.get("min_dist", 0.0))
            max_d = float(payload.get("max_dist", 999.0))
            for (x, y), p in self.grid.items():
                d = math.sqrt((x - clue_x) ** 2 + (y - clue_y) ** 2)
                if d < min_d or d > max_d:
                    self.grid[(x, y)] = p * 0.01  # Heavy discount

        elif clue_type == "sector_elimination":
            # e.g., eliminated quadrant or bounding box
            elim_x_min = payload.get("x_min", -1)
            elim_x_max = payload.get("x_max", -1)
            elim_y_min = payload.get("y_min", -1)
            elim_y_max = payload.get("y_max", -1)
            for (x, y), p in self.grid.items():
                if elim_x_min <= x <= elim_x_max and elim_y_min <= y <= elim_y_max:
                    self.grid[(x, y)] = 0.0

        elif clue_type == "heading":
            # Heading cone from clue location
            min_ang = float(payload.get("bearing_range", [0, 360])[0])
            max_ang = float(payload.get("bearing_range", [0, 360])[1])
            for (x, y), p in self.grid.items():
                dx = x - clue_x
                dy = y - clue_y
                if dx == 0 and dy == 0:
                    continue
                ang = math.degrees(math.atan2(dy, dx)) % 360.0
                if min_ang <= max_ang:
                    in_range = (min_ang <= ang <= max_ang)
                else:
                    in_range = (ang >= min_ang or ang <= max_ang)
                if not in_range:
                    self.grid[(x, y)] = p * 0.05

        elif clue_type == "status_telemetry":
            reported_status = payload.get("status")
            if reported_status and reported_status in self.status_belief:
                for s in self.status_belief:
                    if s == reported_status:
                        self.status_belief[s] = 0.95
                    else:
                        self.status_belief[s] = 0.05 / (len(self.status_belief) - 1)

        self._normalize()
        self.entropy_history.append(self.compute_entropy())

    def _normalize(self):
        """Normalize probability distribution so total sum equals 1.0."""
        total = sum(self.grid.values())
        if total > 0.0:
            for k in self.grid:
                self.grid[k] /= total
        else:
            # Fallback uniform if degenerated
            valid = [k for k in self.grid if k not in self.known_obstacles]
            p = 1.0 / len(valid) if valid else 1.0 / len(self.grid)
            for k in self.grid:
                self.grid[k] = p if k in valid else 0.0

    def compute_entropy(self) -> float:
        """Compute Shannon entropy H(P) = - sum(p * log2(p))."""
        entropy = 0.0
        for p in self.grid.values():
            if p > 1e-12:
                entropy -= p * math.log2(p)
        return entropy

    def get_summary(self, top_n: int = 3) -> BeliefSummary:
        """Get summary snapshot of the current belief state."""
        sorted_cells = sorted(self.grid.items(), key=lambda item: item[1], reverse=True)
        best_coord, max_p = sorted_cells[0]
        top_candidates = sorted_cells[:top_n]
        entropy = self.compute_entropy()

        # Inferred status
        best_status = max(self.status_belief.items(), key=lambda item: item[1])

        # Credible radius (radius around best_coord that encompasses 90% probability mass)
        cumulative_p = 0.0
        max_dist_in_credible = 0.0
        for (x, y), p in sorted_cells:
            cumulative_p += p
            d = math.sqrt((x - best_coord[0]) ** 2 + (y - best_coord[1]) ** 2)
            if d > max_dist_in_credible:
                max_dist_in_credible = d
            if cumulative_p >= 0.90:
                break

        return BeliefSummary(
            entropy=entropy,
            max_prob=max_p,
            best_estimate=best_coord,
            top_candidates=top_candidates,
            inferred_status=best_status[0],
            status_confidence=best_status[1],
            credible_radius=max_dist_in_credible,
        )

    def get_probability_matrix(self) -> List[List[float]]:
        """Return 2D matrix of shape [height][width] with probability values."""
        matrix: List[List[float]] = [[0.0 for _ in range(self.width)] for _ in range(self.height)]
        for (x, y), p in self.grid.items():
            matrix[y][x] = round(p, 6)
        return matrix
