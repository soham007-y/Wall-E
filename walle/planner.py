"""Pathfinding, safety budgeting, and goal arbitration for WALL-E."""

from __future__ import annotations
import heapq
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from walle.config import ResourceConfig


@dataclass
class PathResult:
    """Result of pathfinding search."""
    path: List[Tuple[int, int]]
    cost: int
    found: bool


class GridPlanner:
    """A* pathfinder with dynamic safety budgeting for battery conservation."""

    def __init__(self, width: int, height: int, resources: ResourceConfig):
        self.width = width
        self.height = height
        self.resources = resources

    def astar(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        known_obstacles: Set[Tuple[int, int]]
    ) -> PathResult:
        """Find obstacle-free shortest path from start to goal."""
        if start == goal:
            return PathResult(path=[start], cost=0, found=True)

        if goal in known_obstacles:
            # If goal is an obstacle, cannot navigate inside it
            return PathResult(path=[], cost=9999, found=False)

        open_set: List[Tuple[float, int, Tuple[int, int]]] = []
        counter = 0
        heapq.heappush(open_set, (0.0, counter, start))

        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], int] = {start: 0}
        f_score: Dict[Tuple[int, int], float] = {start: float(self._heuristic(start, goal))}

        while open_set:
            _, _, current = heapq.heappop(open_set)

            if current == goal:
                path = self._reconstruct_path(came_from, current)
                return PathResult(path=path, cost=g_score[current], found=True)

            for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]:
                neighbor = (current[0] + dx, current[1] + dy)

                if not (0 <= neighbor[0] < self.width and 0 <= neighbor[1] < self.height):
                    continue
                if neighbor in known_obstacles:
                    continue

                tentative_g = g_score[current] + self.resources.move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self._heuristic(neighbor, goal) * self.resources.move_cost
                    f_score[neighbor] = f
                    counter += 1
                    heapq.heappush(open_set, (f, counter, neighbor))

        return PathResult(path=[], cost=9999, found=False)

    def find_nearest_recharge_station(
        self,
        current_pos: Tuple[int, int],
        stations: Set[Tuple[int, int]],
        known_obstacles: Set[Tuple[int, int]]
    ) -> Tuple[Optional[Tuple[int, int]], int]:
        """Find the nearest reachable recharge station and its battery cost."""
        if not stations:
            return None, 0

        best_station: Optional[Tuple[int, int]] = None
        min_cost = 999999

        for station in stations:
            res = self.astar(current_pos, station, known_obstacles)
            if res.found and res.cost < min_cost:
                min_cost = res.cost
                best_station = station

        return best_station, min_cost if best_station is not None else 999999

    def check_battery_safety(
        self,
        current_pos: Tuple[int, int],
        current_battery: int,
        stations: Set[Tuple[int, int]],
        known_obstacles: Set[Tuple[int, int]]
    ) -> Tuple[bool, int, Optional[Tuple[int, int]]]:
        """
        Determines if battery level is critically close to the point-of-no-return.
        Returns: (is_critical, return_cost, nearest_station)
        """
        if not stations or current_pos in stations:
            return False, 0, None

        nearest_station, cost = self.find_nearest_recharge_station(current_pos, stations, known_obstacles)
        if nearest_station is None:
            return False, 0, None

        safety_threshold = cost + self.resources.safety_margin
        is_critical = (current_battery <= safety_threshold)
        return is_critical, cost, nearest_station

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        """Manhattan distance heuristic."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _reconstruct_path(
        self,
        came_from: Dict[Tuple[int, int], Tuple[int, int]],
        current: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """Reconstruct path from came_from mapping."""
        total_path = [current]
        while current in came_from:
            current = came_from[current]
            total_path.append(current)
        total_path.reverse()
        return total_path
