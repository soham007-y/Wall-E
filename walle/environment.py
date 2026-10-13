"""Simulated grid environment for WALL-E and EVE exploration."""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from walle.config import ClueData, MissionConfig


class ActionType(str, Enum):
    MOVE_N = "MOVE_N"
    MOVE_S = "MOVE_S"
    MOVE_E = "MOVE_E"
    MOVE_W = "MOVE_W"
    SCAN = "SCAN"
    INSPECT = "INSPECT"
    RECHARGE = "RECHARGE"
    WAIT = "WAIT"


DIRECTION_OFFSETS: Dict[ActionType, Tuple[int, int]] = {
    ActionType.MOVE_N: (0, -1),
    ActionType.MOVE_S: (0, 1),
    ActionType.MOVE_E: (1, 0),
    ActionType.MOVE_W: (-1, 0),
}


class MissionStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS_FOUND_EVE = "SUCCESS_FOUND_EVE"
    FAILED_BATTERY_DEPLETED = "FAILED_BATTERY_DEPLETED"
    FAILED_TIMEOUT = "FAILED_TIMEOUT"


@dataclass
class Observation:
    """Information visible to WALL-E at the current step (strictly no ground-truth leak)."""
    position: Tuple[int, int]
    battery: int
    time_tick: int
    rssi: Optional[float] = None
    bearing_deg: Optional[float] = None
    visible_tiles: Dict[Tuple[int, int], str] = field(default_factory=dict)
    nearby_clue_available: bool = False
    inspected_clue: Optional[Dict[str, Any]] = None
    at_recharge_station: bool = False
    mission_status: MissionStatus = MissionStatus.IN_PROGRESS
    status_message: str = ""


class WallEEnvironment:
    """Simulated physical environment holding true world state and enforcing physics constraints."""

    def __init__(self, config: MissionConfig, seed: Optional[int] = None):
        self.config = config
        self.rng = random.Random(seed if seed is not None else config.seed)

        # Map geometry & entities
        self.width = config.map_config.width
        self.height = config.map_config.height
        self.obstacles: Set[Tuple[int, int]] = set(config.map_config.obstacles)
        self.recharge_stations: Set[Tuple[int, int]] = set(config.map_config.recharge_stations)
        self.eve_true_position = config.map_config.eve_position
        self.eve_status = config.map_config.eve_status
        self.clues: Dict[Tuple[int, int], ClueData] = {
            (c.x, c.y): c for c in config.map_config.clues
        }
        self.decoys = list(config.map_config.decoys)

        # Simulation state
        self.walle_pos = config.map_config.walle_start
        self.battery = config.resources.initial_battery
        self.time_tick = 0
        self.mission_status = MissionStatus.IN_PROGRESS
        self.discovered_clues: Set[str] = set()
        self.explored_tiles: Set[Tuple[int, int]] = {self.walle_pos}

        # Latest signal reading
        self.last_rssi: Optional[float] = None
        self.last_bearing: Optional[float] = None

    def reset(self) -> Observation:
        """Reset environment to initial state and return initial observation."""
        self.walle_pos = self.config.map_config.walle_start
        self.battery = self.config.resources.initial_battery
        self.time_tick = 0
        self.mission_status = MissionStatus.IN_PROGRESS
        self.discovered_clues = set()
        self.explored_tiles = {self.walle_pos}

        # Initial signal reading at spawn point (passive initial reception)
        self.last_rssi, self.last_bearing = self._compute_signal(self.walle_pos)

        return self._build_observation(status_message="Mission initialized. Initial beacon ping received.")

    def step(self, action: ActionType) -> Tuple[Observation, Dict[str, Any]]:
        """Execute one action, update physics, and return observation and step metadata."""
        if self.mission_status != MissionStatus.IN_PROGRESS:
            return self._build_observation(status_message="Mission already ended."), {"cost": 0, "success": False}

        cost = 0
        time_elapsed = 1
        action_success = True
        status_msg = ""
        inspected_clue_payload = None

        if action in DIRECTION_OFFSETS:
            dx, dy = DIRECTION_OFFSETS[action]
            target_x = self.walle_pos[0] + dx
            target_y = self.walle_pos[1] + dy
            cost = self.config.resources.move_cost

            # Check boundary and obstacles
            if not (0 <= target_x < self.width and 0 <= target_y < self.height):
                action_success = False
                status_msg = f"Collision warning: Wall boundary at ({target_x}, {target_y})."
            elif (target_x, target_y) in self.obstacles:
                action_success = False
                status_msg = f"Collision warning: Dense scrap obstacle at ({target_x}, {target_y})."
            else:
                self.walle_pos = (target_x, target_y)
                self.explored_tiles.add(self.walle_pos)
                status_msg = f"Moved to {self.walle_pos}."

        elif action == ActionType.SCAN:
            cost = self.config.resources.scan_cost
            self.last_rssi, self.last_bearing = self._compute_signal(self.walle_pos)
            status_msg = f"Deep radar ping: RSSI {self.last_rssi:.1f} dBm, bearing {self.last_bearing:.1f}°."

        elif action == ActionType.INSPECT:
            cost = self.config.resources.inspect_cost
            # Look for clue at current or adjacent tile
            found_clue: Optional[ClueData] = None
            for offset_x in [0, -1, 1]:
                for offset_y in [0, -1, 1]:
                    check_pos = (self.walle_pos[0] + offset_x, self.walle_pos[1] + offset_y)
                    if check_pos in self.clues and self.clues[check_pos].id not in self.discovered_clues:
                        found_clue = self.clues[check_pos]
                        break
                if found_clue:
                    break

            if found_clue:
                self.discovered_clues.add(found_clue.id)
                inspected_clue_payload = {
                    "id": found_clue.id,
                    "x": found_clue.x,
                    "y": found_clue.y,
                    "description": found_clue.description,
                    "type": found_clue.clue_type,
                    "payload": found_clue.payload,
                }
                status_msg = f"Clue deciphered [{found_clue.id}]: '{found_clue.description}'."
            else:
                status_msg = "Inspected area: No new clue signatures detected in immediate vicinity."

        elif action == ActionType.RECHARGE:
            time_elapsed = self.config.resources.recharge_time_cost
            if self.walle_pos in self.recharge_stations:
                old_bat = self.battery
                self.battery = min(
                    self.config.resources.max_battery,
                    self.battery + self.config.resources.recharge_rate
                )
                cost = 0  # Recharging restores battery
                status_msg = f"Solar panels deployed. Recharged from {old_bat}% to {self.battery}%."
            else:
                cost = 1  # Small idle loss if trying to recharge outside station
                status_msg = "Recharge failed: Not positioned on a solar recharge zone."

        elif action == ActionType.WAIT:
            cost = 1
            time_elapsed = 1
            status_msg = "Idling in place."

        # Apply battery consumption
        self.battery = max(0, self.battery - cost)
        self.time_tick += time_elapsed

        # Check mission status conditions
        if self.walle_pos == self.eve_true_position:
            self.mission_status = MissionStatus.SUCCESS_FOUND_EVE
            status_msg += " TARGET CONFIRMED: EVE located!"
        elif self.battery <= 0:
            self.mission_status = MissionStatus.FAILED_BATTERY_DEPLETED
            status_msg += " CRITICAL FAILURE: Battery depleted."
        elif self.time_tick >= self.config.resources.max_time_ticks:
            self.mission_status = MissionStatus.FAILED_TIMEOUT
            status_msg += " MISSION TIMEOUT: Time limit reached."

        obs = self._build_observation(
            status_message=status_msg,
            inspected_clue=inspected_clue_payload
        )
        metadata = {
            "action": action.value,
            "cost": cost,
            "success": action_success,
            "battery": self.battery,
            "time_tick": self.time_tick,
            "position": self.walle_pos,
        }
        return obs, metadata

    def _build_observation(
        self,
        status_message: str = "",
        inspected_clue: Optional[Dict[str, Any]] = None
    ) -> Observation:
        """Construct observation for WALL-E containing only local & sensor percepts."""
        # Vision radius: 1 tile in 8 directions around WALL-E
        visible_tiles: Dict[Tuple[int, int], str] = {}
        nearby_clue = False

        for dy in range(-1, 2):
            for dx in range(-1, 2):
                coord = (self.walle_pos[0] + dx, self.walle_pos[1] + dy)
                if 0 <= coord[0] < self.width and 0 <= coord[1] < self.height:
                    self.explored_tiles.add(coord)
                    if coord in self.obstacles:
                        visible_tiles[coord] = "#"
                    elif coord in self.recharge_stations:
                        visible_tiles[coord] = "R"
                    elif coord in self.clues and self.clues[coord].id not in self.discovered_clues:
                        visible_tiles[coord] = "?"
                        nearby_clue = True
                    elif coord == self.eve_true_position:
                        visible_tiles[coord] = "E"
                    else:
                        visible_tiles[coord] = "."

        return Observation(
            position=self.walle_pos,
            battery=self.battery,
            time_tick=self.time_tick,
            rssi=self.last_rssi,
            bearing_deg=self.last_bearing,
            visible_tiles=visible_tiles,
            nearby_clue_available=nearby_clue,
            inspected_clue=inspected_clue,
            at_recharge_station=(self.walle_pos in self.recharge_stations),
            mission_status=self.mission_status,
            status_message=status_message,
        )

    def _compute_signal(self, pos: Tuple[int, int]) -> Tuple[float, float]:
        """Calculate RSSI and bearing to EVE based on physics, LOS occlusions, and noise."""
        target_pos = self.eve_true_position

        dx = target_pos[0] - pos[0]
        dy = target_pos[1] - pos[1]
        dist = math.sqrt(dx * dx + dy * dy)

        # Log-distance path loss: RSSI = P0 - 10 * eta * log10(max(d, 1))
        p0 = self.config.sensor.p0
        eta = self.config.sensor.eta
        effective_dist = max(dist, 1.0)
        base_rssi = p0 - 10.0 * eta * math.log10(effective_dist)

        # Obstacle attenuation along line-of-sight
        obstacle_count = 0
        if self.config.sensor.los_check and dist > 1.0:
            obstacle_count = self._count_obstacles_along_los(pos, target_pos)
            base_rssi -= obstacle_count * self.config.sensor.obstacle_attenuation_db

        # Gaussian measurement noise
        noise = self.rng.gauss(0.0, self.config.sensor.rssi_noise_std)
        rssi = base_rssi + noise

        # Bearing in degrees: 0° is East (+X), 90° is South (+Y)
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad) % 360.0
        bearing_noise = self.rng.gauss(0.0, self.config.sensor.bearing_noise_std_deg)
        bearing = (angle_deg + bearing_noise) % 360.0

        return rssi, bearing

    def _count_obstacles_along_los(self, start: Tuple[int, int], end: Tuple[int, int]) -> int:
        """Count obstacles along line of sight using Bresenham's line algorithm."""
        x0, y0 = start
        x1, y1 = end
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        count = 0
        curr_x, curr_y = x0, y0

        while (curr_x, curr_y) != (x1, y1):
            if (curr_x, curr_y) != (x0, y0) and (curr_x, curr_y) in self.obstacles:
                count += 1
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                curr_x += sx
            if e2 < dx:
                err += dx
                curr_y += sy

        return count

    def get_ground_truth_for_eval(self) -> Dict[str, Any]:
        """Provides ground truth for post-mission verification only."""
        return {
            "eve_true_position": self.eve_true_position,
            "eve_status": self.eve_status,
            "total_clues": len(self.clues),
            "discovered_clues_count": len(self.discovered_clues),
            "obstacles_count": len(self.obstacles),
            "recharge_stations": list(self.recharge_stations),
        }
