"""ANSI colorized terminal visualizer for WALL-E mission tracking and playback."""

from __future__ import annotations
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

from walle.config import MissionConfig
from walle.environment import Observation
from walle.logger import StepTrace


class TerminalColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    BG_DARK = "\033[40m"
    BG_YELLOW = "\033[43m"
    BG_CYAN = "\033[46m"


class AsciiVisualizer:
    """Renders a real-time ASCII map and telemetry HUD in the terminal."""

    def __init__(self, config: MissionConfig):
        self.config = config
        self.width = config.map_config.width
        self.height = config.map_config.height
        self.obstacles = set(config.map_config.obstacles)
        self.recharge_stations = set(config.map_config.recharge_stations)
        self.clues = { (c.x, c.y): c for c in config.map_config.clues }
        self.visited_tiles: Set[Tuple[int, int]] = set()

    def render_step(
        self,
        trace: StepTrace,
        prob_matrix: Optional[List[List[float]]] = None,
        clear_screen: bool = False
    ):
        """Render complete map frame and telemetry HUD."""
        self.visited_tiles.add(trace.position)
        c = TerminalColors

        lines: List[str] = []
        if clear_screen:
            lines.append("\033[2J\033[H")

        lines.append(f"{c.BOLD}{c.CYAN}=== 🤖 WALL-E MISSION MONITOR: {self.config.name} ==={c.RESET}")

        # Top border
        lines.append("  +" + "---" * self.width + "+")

        # Grid rows
        for y in range(self.height):
            row_str = f"{y:2d}|"
            for x in range(self.width):
                pos = (x, y)
                cell = "   "

                if pos == trace.position:
                    cell = f"{c.BOLD}{c.YELLOW}[W]{c.RESET}"
                elif pos in self.recharge_stations:
                    cell = f"{c.GREEN} ⚡{c.RESET}"
                elif pos in self.obstacles:
                    cell = f"{c.DIM}███{c.RESET}"
                elif pos in self.clues:
                    cell = f"{c.MAGENTA} ? {c.RESET}"
                elif pos == trace.belief_peak_coord and trace.belief_peak_prob > 0.25:
                    cell = f"{c.RED} * {c.RESET}"
                elif pos in self.visited_tiles:
                    cell = f"{c.CYAN} · {c.RESET}"
                else:
                    # Fog / unexplored
                    cell = f"{c.DIM} . {c.RESET}"

                row_str += cell
            row_str += "|"
            lines.append(row_str)

        # Bottom border
        lines.append("  +" + "---" * self.width + "+")
        col_indices = "   " + "".join(f"{x:3d}" for x in range(self.width))
        lines.append(f"{c.DIM}{col_indices}{c.RESET}")

        # Telemetry HUD
        bat_blocks = int(trace.battery_after / 10)
        bat_bar = f"{c.GREEN}{'█' * bat_blocks}{c.DIM}{'░' * (10 - bat_blocks)}{c.RESET}"

        lines.append("")
        lines.append(f"{c.BOLD}TELEMETRY HUD{c.RESET}")
        lines.append(f"  Step: {trace.step_number:03d} | Tick: {trace.time_tick:03d} | Mode: {c.BOLD}{trace.agent_mode}{c.RESET}")
        lines.append(f"  Position: {trace.position} | Target: {trace.target_coord} | Action: {c.YELLOW}{trace.action}{c.RESET} (Cost: {trace.action_cost})")
        lines.append(f"  Battery: [{bat_bar}] {trace.battery_after}%")
        lines.append(f"  Entropy: {trace.belief_entropy:.2f} bits | Peak Est: {trace.belief_peak_coord} ({trace.belief_peak_prob*100:.1f}%)")
        lines.append(f"  Inferred Status: {c.CYAN}{trace.inferred_status}{c.RESET}")
        lines.append(f"  Reasoning: {c.DIM}{trace.agent_reasoning}{c.RESET}")
        if trace.inspected_clue:
            lines.append(f"  {c.BOLD}{c.MAGENTA}🔍 CLUE DISCOVERED: {trace.inspected_clue.get('description')}{c.RESET}")
        lines.append("=" * 60)

        output = "\n".join(lines)
        print(output)
        sys.stdout.flush()

    def replay_traces(self, traces: List[StepTrace], delay: float = 0.1):
        """Replay recorded traces frame-by-frame."""
        for trace in traces:
            self.render_step(trace, clear_screen=True)
            time.sleep(delay)
