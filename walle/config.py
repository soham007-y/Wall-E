"""Configuration schemas and loaders for WALL-E mission simulation."""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ResourceConfig:
    """Resource budget and action cost parameters."""
    initial_battery: int = 100
    max_battery: int = 100
    max_time_ticks: int = 150
    move_cost: int = 2
    scan_cost: int = 4
    inspect_cost: int = 3
    recharge_rate: int = 15
    recharge_time_cost: int = 1
    safety_margin: int = 6  # Extra battery buffer for return trips


@dataclass
class SensorConfig:
    """Sensor physics and noise profile."""
    # Log-distance path loss parameters: RSSI = P0 - 10 * eta * log10(max(d, 1))
    p0: float = -20.0  # Signal strength at distance 1
    eta: float = 2.0   # Path loss exponent (free space ~ 2.0, cluttered ~ 3.0)
    rssi_noise_std: float = 1.5
    bearing_noise_std_deg: float = 10.0  # Directional angle noise in degrees
    obstacle_attenuation_db: float = 4.0  # Decibels lost per obstacle along LOS
    scan_radius: float = 25.0  # Maximum sensor sensitivity radius
    los_check: bool = True     # Whether obstacles attenuate signal line-of-sight


@dataclass
class ClueData:
    """A qualitative or spatial clue present in the environment."""
    id: str
    x: int
    y: int
    description: str
    clue_type: str  # 'distance_bound', 'sector_elimination', 'status_telemetry', 'landmark', 'heading'
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MapConfig:
    """Map dimensions, obstacles, charging locations, and entity spawns."""
    width: int = 20
    height: int = 20
    walle_start: Tuple[int, int] = (1, 1)
    eve_position: Tuple[int, int] = (16, 16)
    eve_status: str = "DORMANT_REBOOT_REQUIRED"
    obstacles: List[Tuple[int, int]] = field(default_factory=list)
    recharge_stations: List[Tuple[int, int]] = field(default_factory=list)
    clues: List[ClueData] = field(default_factory=list)
    decoys: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MissionConfig:
    """Complete mission configuration."""
    name: str
    description: str
    map_config: MapConfig
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    sensor: SensorConfig = field(default_factory=SensorConfig)
    seed: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MissionConfig:
        """Parse dictionary into typed MissionConfig."""
        map_raw = data.get("map", {})
        res_raw = data.get("resources", {})
        sensor_raw = data.get("sensor", {})

        # Parse clues
        clues_list = []
        for c in map_raw.get("clues", []):
            clues_list.append(ClueData(
                id=str(c.get("id", f"clue_{len(clues_list)}")),
                x=int(c["x"]),
                y=int(c["y"]),
                description=str(c.get("description", "")),
                clue_type=str(c.get("type", "general")),
                payload=c.get("payload", {})
            ))

        # Parse obstacles & stations
        obstacles = [tuple(pt) for pt in map_raw.get("obstacles", [])]
        stations = [tuple(pt) for pt in map_raw.get("recharge_stations", [])]
        walle_start = tuple(map_raw.get("walle_start", [0, 0]))
        eve_pos = tuple(map_raw.get("eve_position", [map_raw.get("width", 10) - 1, map_raw.get("height", 10) - 1]))

        map_config = MapConfig(
            width=int(map_raw.get("width", 20)),
            height=int(map_raw.get("height", 20)),
            walle_start=(int(walle_start[0]), int(walle_start[1])),
            eve_position=(int(eve_pos[0]), int(eve_pos[1])),
            eve_status=str(map_raw.get("eve_status", "DORMANT_REBOOT_REQUIRED")),
            obstacles=[(int(pt[0]), int(pt[1])) for pt in obstacles],
            recharge_stations=[(int(pt[0]), int(pt[1])) for pt in stations],
            clues=clues_list,
            decoys=map_raw.get("decoys", [])
        )

        resources = ResourceConfig(
            initial_battery=int(res_raw.get("initial_battery", 100)),
            max_battery=int(res_raw.get("max_battery", 100)),
            max_time_ticks=int(res_raw.get("max_time_ticks", 150)),
            move_cost=int(res_raw.get("move_cost", 2)),
            scan_cost=int(res_raw.get("scan_cost", 4)),
            inspect_cost=int(res_raw.get("inspect_cost", 3)),
            recharge_rate=int(res_raw.get("recharge_rate", 15)),
            recharge_time_cost=int(res_raw.get("recharge_time_cost", 1)),
            safety_margin=int(res_raw.get("safety_margin", 6))
        )

        sensor = SensorConfig(
            p0=float(sensor_raw.get("p0", -20.0)),
            eta=float(sensor_raw.get("eta", 2.0)),
            rssi_noise_std=float(sensor_raw.get("rssi_noise_std", 1.5)),
            bearing_noise_std_deg=float(sensor_raw.get("bearing_noise_std_deg", 10.0)),
            obstacle_attenuation_db=float(sensor_raw.get("obstacle_attenuation_db", 4.0)),
            scan_radius=float(sensor_raw.get("scan_radius", 25.0)),
            los_check=bool(sensor_raw.get("los_check", True))
        )

        return cls(
            name=str(data.get("name", "Untitled Mission")),
            description=str(data.get("description", "")),
            map_config=map_config,
            resources=resources,
            sensor=sensor,
            seed=data.get("seed"),
            metadata=data.get("metadata", {})
        )

    @classmethod
    def load(cls, file_path: str) -> MissionConfig:
        """Load configuration from JSON or YAML file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Config file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        # Try parsing JSON first
        try:
            data = json.loads(content)
            return cls.from_dict(data)
        except json.JSONDecodeError:
            pass

        # Try YAML if available or fallback parser
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(content)
            return cls.from_dict(data)
        except ImportError:
            raise ValueError(f"File {file_path} is not valid JSON and PyYAML is not installed.")

    def to_dict(self) -> Dict[str, Any]:
        """Convert back to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "seed": self.seed,
            "map": {
                "width": self.map_config.width,
                "height": self.map_config.height,
                "walle_start": list(self.map_config.walle_start),
                "eve_position": list(self.map_config.eve_position),
                "eve_status": self.map_config.eve_status,
                "obstacles": [list(pt) for pt in self.map_config.obstacles],
                "recharge_stations": [list(pt) for pt in self.map_config.recharge_stations],
                "clues": [
                    {
                        "id": c.id,
                        "x": c.x,
                        "y": c.y,
                        "description": c.description,
                        "type": c.clue_type,
                        "payload": c.payload
                    }
                    for c in self.map_config.clues
                ],
                "decoys": self.map_config.decoys
            },
            "resources": {
                "initial_battery": self.resources.initial_battery,
                "max_battery": self.resources.max_battery,
                "max_time_ticks": self.resources.max_time_ticks,
                "move_cost": self.resources.move_cost,
                "scan_cost": self.resources.scan_cost,
                "inspect_cost": self.resources.inspect_cost,
                "recharge_rate": self.resources.recharge_rate,
                "recharge_time_cost": self.resources.recharge_time_cost,
                "safety_margin": self.resources.safety_margin
            },
            "sensor": {
                "p0": self.sensor.p0,
                "eta": self.sensor.eta,
                "rssi_noise_std": self.sensor.rssi_noise_std,
                "bearing_noise_std_deg": self.sensor.bearing_noise_std_deg,
                "obstacle_attenuation_db": self.sensor.obstacle_attenuation_db,
                "scan_radius": self.sensor.scan_radius,
                "los_check": self.sensor.los_check
            },
            "metadata": self.metadata
        }
