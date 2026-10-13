"""Interactive 3D WebGL / Three.js Visualizer Generator for WALL-E and EVE exploration."""

from __future__ import annotations
import json
import math
import os
from typing import Any, Dict, List, Optional

from walle.agent import AutonomousWallEAgent
from walle.config import MissionConfig
from walle.environment import MissionStatus, WallEEnvironment
from walle.logger import MissionLogger
from walle.report import MissionReportGenerator


class ThreeJsVisualizerGenerator:
    """Generates a complete, interactive 3D WebGL website using Three.js."""

    @staticmethod
    def collect_mission_data(config_path: str) -> Dict[str, Any]:
        """Run or simulate mission to gather full 3D trace data including probability matrices."""
        config = MissionConfig.load(config_path)
        env = WallEEnvironment(config, seed=config.seed)
        agent = AutonomousWallEAgent(config)
        logger = MissionLogger(config.name, verbose=False)

        prob_history = []
        obs = env.reset()
        step = 0
        prob_history.append(agent.belief.get_probability_matrix())

        while obs.mission_status == MissionStatus.IN_PROGRESS and step < config.resources.max_time_ticks:
            step += 1
            obs_before = obs
            decision = agent.decide_action(obs_before)
            obs_after, meta = env.step(decision.action)
            summary = agent.latest_summary
            logger.log_step(step, obs_before, decision, obs_after, meta, summary)
            prob_history.append(agent.belief.get_probability_matrix())
            obs = obs_after

        report_gen = MissionReportGenerator(
            config=config,
            traces=logger.traces,
            final_summary=agent.latest_summary,
            mission_status=obs.mission_status,
            ground_truth=env.get_ground_truth_for_eval()
        )

        return {
            "name": config.name,
            "description": config.description,
            "config": config.to_dict(),
            "traces": [t.__dict__ for t in logger.traces],
            "metrics": report_gen.metrics.__dict__,
            "report_markdown": report_gen.generate_markdown(),
            "prob_history": prob_history,
            "ground_truth": env.get_ground_truth_for_eval()
        }

    @classmethod
    def generate_html(cls, missions_bundle: Dict[str, Dict[str, Any]]) -> str:
        """Render complete 3D WebGL website HTML."""
        bundle_json = json.dumps(missions_bundle)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WALL-E & EVE: 3D Mission Operations Center</title>
<!-- Three.js and OrbitControls from standard CDN -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<style>
  :root {{
    --bg-dark: #070a12;
    --panel-bg: rgba(14, 21, 37, 0.82);
    --panel-border: rgba(0, 240, 255, 0.25);
    --cyan: #00f0ff;
    --yellow: #ffd000;
    --green: #00ff88;
    --red: #ff3366;
    --purple: #bf5af2;
    --text: #e6edfa;
    --text-dim: #8a9bb8;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }}
  body, html {{ width: 100%; height: 100%; overflow: hidden; background: var(--bg-dark); color: var(--text); }}
  
  #canvas3d {{ width: 100%; height: 100%; display: block; }}

  /* Top Navigation Overlay */
  .top-bar {{
    position: absolute; top: 0; left: 0; right: 0;
    padding: 14px 24px;
    display: flex; justify-content: space-between; align-items: center;
    background: linear-gradient(180deg, rgba(7, 10, 18, 0.9) 0%, rgba(7, 10, 18, 0.3) 80%, transparent 100%);
    pointer-events: none;
    z-index: 10;
  }}
  .brand {{ display: flex; align-items: center; gap: 12px; pointer-events: auto; }}
  .logo {{ font-size: 28px; filter: drop-shadow(0 0 10px rgba(255, 208, 0, 0.5)); }}
  .title-h1 {{ font-size: 18px; font-weight: 700; letter-spacing: 1px; color: #fff; }}
  .title-sub {{ font-size: 12px; color: var(--cyan); letter-spacing: 0.5px; }}

  .mission-selector {{ pointer-events: auto; display: flex; align-items: center; gap: 10px; }}
  select {{
    background: var(--panel-bg); color: var(--cyan);
    border: 1px solid var(--panel-border); border-radius: 6px;
    padding: 8px 14px; font-size: 13px; font-weight: 600;
    outline: none; cursor: pointer; backdrop-filter: blur(8px);
  }}

  /* Camera Mode Pills */
  .cam-bar {{
    position: absolute; top: 72px; left: 24px;
    display: flex; gap: 8px; z-index: 10;
  }}
  .pill-btn {{
    background: var(--panel-bg); color: var(--text-dim);
    border: 1px solid var(--panel-border); border-radius: 20px;
    padding: 6px 14px; font-size: 12px; cursor: pointer;
    backdrop-filter: blur(8px); transition: all 0.2s;
  }}
  .pill-btn:hover {{ color: var(--cyan); border-color: var(--cyan); }}
  .pill-btn.active {{ background: rgba(0, 240, 255, 0.2); color: var(--cyan); border-color: var(--cyan); font-weight: 600; box-shadow: 0 0 12px rgba(0, 240, 255, 0.3); }}

  /* Bottom Playback Control Deck */
  .control-deck {{
    position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
    width: min(880px, calc(100% - 40px));
    background: var(--panel-bg); border: 1px solid var(--panel-border);
    border-radius: 12px; padding: 14px 20px;
    backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
    display: flex; flex-direction: column; gap: 10px;
    z-index: 10;
  }}
  .slider-wrapper {{ display: flex; align-items: center; gap: 14px; }}
  .step-label {{ font-size: 13px; font-weight: 700; color: var(--cyan); width: 85px; }}
  input[type=range] {{
    flex: 1; accent-color: var(--cyan); height: 6px; cursor: pointer;
    background: rgba(255, 255, 255, 0.1); border-radius: 3px;
  }}
  .deck-actions {{ display: flex; justify-content: space-between; align-items: center; }}
  .btn-grp {{ display: flex; gap: 8px; }}
  .action-btn {{
    background: rgba(255, 255, 255, 0.05); color: #fff;
    border: 1px solid var(--panel-border); border-radius: 6px;
    padding: 7px 16px; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: all 0.2s;
  }}
  .action-btn:hover {{ border-color: var(--cyan); color: var(--cyan); }}
  .action-btn.active {{ background: rgba(0, 240, 255, 0.25); color: var(--cyan); border-color: var(--cyan); }}

  /* Left Intel HUD Card */
  .intel-hud {{
    position: absolute; top: 120px; left: 24px; width: 310px;
    background: var(--panel-bg); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 16px;
    backdrop-filter: blur(10px); box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    z-index: 10; display: flex; flex-direction: column; gap: 12px;
  }}
  .hud-title {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--cyan); font-weight: 700; }}
  .stat-row {{ display: flex; justify-content: space-between; align-items: center; font-size: 13px; }}
  .stat-label {{ color: var(--text-dim); }}
  .stat-val {{ font-weight: 700; color: #fff; }}

  /* Battery Meter */
  .battery-bar {{ width: 100%; height: 10px; background: rgba(0,0,0,0.4); border-radius: 5px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); margin-top: 4px; }}
  .battery-fill {{ height: 100%; width: 100%; background: var(--green); transition: width 0.3s; }}

  /* Thought bubble / Rationale */
  .thought-card {{
    background: rgba(0, 240, 255, 0.06); border-left: 3px solid var(--cyan);
    padding: 10px; border-radius: 4px; font-size: 12px; line-height: 1.5; color: #d0e0ff;
  }}

  /* Right Side Tabs / Clue Drawer */
  .side-panel {{
    position: absolute; top: 80px; right: 24px; width: 340px; max-height: calc(100vh - 120px);
    background: var(--panel-bg); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 16px; overflow-y: auto;
    backdrop-filter: blur(10px); box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    z-index: 10; display: flex; flex-direction: column; gap: 12px;
  }}
  .tab-header {{ display: flex; border-bottom: 1px solid var(--panel-border); margin-bottom: 8px; }}
  .tab-link {{
    flex: 1; padding: 8px; text-align: center; font-size: 12px; font-weight: 600;
    color: var(--text-dim); background: none; border: none; cursor: pointer;
    border-bottom: 2px solid transparent;
  }}
  .tab-link.active {{ color: var(--cyan); border-bottom-color: var(--cyan); }}
  .tab-pane {{ display: none; }}
  .tab-pane.active {{ display: block; }}

  .clue-badge {{ display: inline-block; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 3px; background: rgba(191, 90, 242, 0.2); color: var(--purple); border: 1px solid var(--purple); margin-bottom: 4px; }}
  .clue-box {{ background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 10px; margin-bottom: 8px; font-size: 12px; }}

  /* Modal for Full Report */
  .modal-overlay {{
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75);
    backdrop-filter: blur(6px); z-index: 100; justify-content: center; align-items: center;
  }}
  .modal-box {{
    width: min(800px, 90vw); max-height: 85vh; background: #0c1220;
    border: 1px solid var(--cyan); border-radius: 12px; padding: 24px;
    overflow-y: auto; box-shadow: 0 0 40px rgba(0, 240, 255, 0.3); position: relative;
  }}
  .close-btn {{ position: absolute; top: 16px; right: 20px; font-size: 22px; cursor: pointer; color: var(--text-dim); background: none; border: none; }}
  pre {{ white-space: pre-wrap; font-size: 13px; line-height: 1.6; color: #ccd6e6; }}
</style>
</head>
<body>

<div class="top-bar">
  <div class="brand">
    <div class="logo">🤖</div>
    <div>
      <div class="title-h1">WALL-E & EVE 3D EXPLORATION</div>
      <div class="title-sub" id="hdrMissionDesc">Autonomous Signal Triangulation & Rescue</div>
    </div>
  </div>
  <div class="mission-selector">
    <span style="font-size: 12px; color: var(--text-dim); font-weight: bold;">MISSION:</span>
    <select id="missionSelect">
      <!-- Generated via JS -->
    </select>
  </div>
</div>

<!-- Camera Mode Buttons -->
<div class="cam-bar">
  <button class="pill-btn active" onclick="setCamMode('orbit')">🎥 Free Orbit</button>
  <button class="pill-btn" onclick="setCamMode('follow')">🤖 Follow WALL-E</button>
  <button class="pill-btn" onclick="setCamMode('top')">🗺️ Tactical Top-Down</button>
  <button class="pill-btn" onclick="setCamMode('first')">👁️ WALL-E Lens</button>
</div>

<!-- Left Intel HUD -->
<div class="intel-hud">
  <div class="hud-title">⚡ REAL-TIME TELEMETRY</div>
  <div class="stat-row">
    <span class="stat-label">Agent Mode:</span>
    <span class="stat-val" id="hudMode" style="color: var(--cyan);">EXPLORATION</span>
  </div>
  <div class="stat-row">
    <span class="stat-label">Coordinates:</span>
    <span class="stat-val" id="hudPos">(0, 0)</span>
  </div>
  <div class="stat-row">
    <span class="stat-label">Belief Peak Target:</span>
    <span class="stat-val" id="hudPeak" style="color: var(--red);">(0, 0)</span>
  </div>
  <div class="stat-row">
    <span class="stat-label">Entropy:</span>
    <span class="stat-val" id="hudEntropy">0.00 bits</span>
  </div>
  <div class="stat-row">
    <span class="stat-label">Peak Confidence:</span>
    <span class="stat-val" id="hudConf">0.0%</span>
  </div>

  <div>
    <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 3px;">
      <span class="stat-label">BATTERY RESERVE</span>
      <span id="hudBatteryPct" style="font-weight: bold; color: var(--green);">100%</span>
    </div>
    <div class="battery-bar">
      <div id="hudBatteryFill" class="battery-fill"></div>
    </div>
  </div>

  <div class="stat-row" style="margin-top: 4px;">
    <span class="stat-label">Inferred EVE State:</span>
    <span class="stat-val" id="hudStatus" style="color: var(--yellow); font-size: 11px;">DORMANT</span>
  </div>

  <div class="thought-card">
    <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--cyan); margin-bottom: 3px;">Tactical Rationale</div>
    <div id="hudThought">Awaiting mission initialization...</div>
  </div>
</div>

<!-- Right Side Intel Drawer -->
<div class="side-panel">
  <div class="tab-header">
    <button class="tab-link active" onclick="switchSideTab('clues')">Dossier (<span id="clueCount">0</span>)</button>
    <button class="tab-link" onclick="switchSideTab('stats')">Mission Intel</button>
  </div>

  <div id="tab-clues" class="tab-pane active">
    <div id="cluesListContainer">
      <!-- Clue boxes inserted here -->
    </div>
  </div>

  <div id="tab-stats" class="tab-pane">
    <div class="stat-row" style="margin-bottom: 8px;">
      <span class="stat-label">Mission Outcome:</span>
      <span class="stat-val" id="statOutcome" style="color: var(--green);">SUCCESS</span>
    </div>
    <div class="stat-row" style="margin-bottom: 8px;">
      <span class="stat-label">Total Steps:</span>
      <span class="stat-val" id="statSteps">0</span>
    </div>
    <div class="stat-row" style="margin-bottom: 8px;">
      <span class="stat-label">Total Distance:</span>
      <span class="stat-val" id="statDistance">0.0 units</span>
    </div>
    <div class="stat-row" style="margin-bottom: 8px;">
      <span class="stat-label">Recharges Conducted:</span>
      <span class="stat-val" id="statRecharges">0</span>
    </div>
    <div class="stat-row" style="margin-bottom: 12px;">
      <span class="stat-label">Localization Error:</span>
      <span class="stat-val" id="statLocError">0.00 tiles</span>
    </div>
    <button class="action-btn" style="width: 100%;" onclick="openReportModal()">📄 View Full Mission Report</button>
  </div>
</div>

<!-- Bottom Control Deck -->
<div class="control-deck">
  <div class="slider-row slider-wrapper">
    <span class="step-label">STEP <span id="lblStep">0</span> / <span id="lblMaxStep">0</span></span>
    <input type="range" id="stepRange" min="0" max="0" value="0">
  </div>
  <div class="deck-actions">
    <div class="btn-grp">
      <button class="action-btn" id="btnPrev">◀ Prev</button>
      <button class="action-btn" id="btnPlay">▶ Play</button>
      <button class="action-btn" id="btnNext">Next ▶</button>
      <button class="action-btn" id="btnReset">Reset</button>
    </div>
    <div class="btn-grp">
      <button class="action-btn active" id="btnHeatmap">3D Heatmap: ON</button>
      <button class="action-btn" id="btnSpeed">1x</button>
      <button class="action-btn" id="btnSound">🔊 Audio: ON</button>
    </div>
  </div>
</div>

<!-- Modal Report Dialog -->
<div id="reportModal" class="modal-overlay">
  <div class="modal-box">
    <button class="close-btn" onclick="closeReportModal()">✕</button>
    <h2 style="color: var(--cyan); margin-bottom: 16px;">🤖 Mission Operations Report</h2>
    <pre id="modalReportPre"></pre>
  </div>
</div>

<!-- WebGL Canvas Container -->
<canvas id="canvas3d"></canvas>

<script>
  // Missions data bundle injected from Python
  const missionsData = {bundle_json};
  let activeMissionKey = Object.keys(missionsData)[0];
  let curData = missionsData[activeMissionKey];

  // Simulation State
  let curStep = 0;
  let isPlaying = false;
  let playTimer = null;
  let speedMultiplier = 1;
  const speedOptions = [1, 2, 5];
  let showHeatmap3D = true;
  let soundEnabled = true;
  let camMode = 'orbit'; // 'orbit', 'follow', 'top', 'first'

  // Web Audio Synthesizer
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  function playBeep(freq = 440, type = 'sine', duration = 0.08) {{
    if (!soundEnabled || !audioCtx) return;
    try {{
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + duration);
    }} catch(e) {{}}
  }}

  // Three.js Scene Setup
  const canvas = document.getElementById('canvas3d');
  const renderer = new THREE.WebGLRenderer({{ canvas, antialias: true }});
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x070b14);
  scene.fog = new THREE.FogExp2(0x0a101f, 0.015);

  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.set(20, 26, 32);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.maxPolarAngle = Math.PI / 2.05;

  // Lighting
  const ambientLight = new THREE.AmbientLight(0x2d3a5a, 1.2);
  scene.add(ambientLight);

  const sunLight = new THREE.DirectionalLight(0xffecd0, 1.5);
  sunLight.position.set(30, 45, 20);
  sunLight.castShadow = true;
  sunLight.shadow.mapSize.width = 2048;
  sunLight.shadow.mapSize.height = 2048;
  sunLight.shadow.camera.near = 10;
  sunLight.shadow.camera.far = 120;
  sunLight.shadow.camera.left = -30;
  sunLight.shadow.camera.right = 30;
  sunLight.shadow.camera.top = 30;
  sunLight.shadow.camera.bottom = -30;
  scene.add(sunLight);

  // Atmospheric dust particles
  const particleGeo = new THREE.BufferGeometry();
  const particleCount = 400;
  const posArray = new Float32Array(particleCount * 3);
  for(let i = 0; i < particleCount * 3; i += 3) {{
    posArray[i] = (Math.random() - 0.5) * 60;
    posArray[i+1] = Math.random() * 15;
    posArray[i+2] = (Math.random() - 0.5) * 60;
  }}
  particleGeo.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
  const particleMat = new THREE.PointsMaterial({{ size: 0.15, color: 0x00f0ff, transparent: true, opacity: 0.4 }});
  const particles = new THREE.Points(particleGeo, particleMat);
  scene.add(particles);

  // Groups for Dynamic Scene Elements
  const worldGroup = new THREE.Group();
  scene.add(worldGroup);

  let walleMesh = null;
  let eveMesh = null;
  let heatmapBarsGroup = new THREE.Group();
  scene.add(heatmapBarsGroup);
  let pathLine = null;
  let clueMeshes = [];
  let stationMeshes = [];

  // Build Procedural WALL-E 3D Model
  function createWallEMesh() {{
    const group = new THREE.Group();

    // Body Chassis (Yellow weathered cube)
    const bodyMat = new THREE.MeshStandardMaterial({{ color: 0xdf9d28, roughness: 0.5, metalness: 0.3 }});
    const bodyGeo = new THREE.BoxGeometry(1.2, 1.0, 1.2);
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 0.7;
    body.castShadow = true;
    group.add(body);

    // Tread Tracks (Left & Right)
    const treadMat = new THREE.MeshStandardMaterial({{ color: 0x1a1e26, roughness: 0.9, metalness: 0.1 }});
    const treadGeo = new THREE.BoxGeometry(0.3, 0.7, 1.4);

    const leftTread = new THREE.Mesh(treadGeo, treadMat);
    leftTread.position.set(-0.75, 0.45, 0);
    leftTread.castShadow = true;
    group.add(leftTread);

    const rightTread = new THREE.Mesh(treadGeo, treadMat);
    rightTread.position.set(0.75, 0.45, 0);
    rightTread.castShadow = true;
    group.add(rightTread);

    // Neck
    const neckMat = new THREE.MeshStandardMaterial({{ color: 0x555e6d, metalness: 0.7 }});
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.6), neckMat);
    neck.position.set(0, 1.4, 0.1);
    group.add(neck);

    // Binocular Eyes Group
    const eyeGroup = new THREE.Group();
    eyeGroup.position.set(0, 1.7, 0.2);

    const eyeFrameMat = new THREE.MeshStandardMaterial({{ color: 0xc88e25, metalness: 0.4 }});
    const lensMat = new THREE.MeshStandardMaterial({{ color: 0x050c18, roughness: 0.1, metalness: 0.9 }});

    // Left Eye
    const leftEye = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.24, 0.45, 16), eyeFrameMat);
    leftEye.rotation.x = Math.PI / 2;
    leftEye.position.set(-0.35, 0, 0);
    const leftLens = new THREE.Mesh(new THREE.CircleGeometry(0.22, 16), lensMat);
    leftLens.position.set(-0.35, 0, 0.23);
    eyeGroup.add(leftEye);
    eyeGroup.add(leftLens);

    // Right Eye
    const rightEye = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.24, 0.45, 16), eyeFrameMat);
    rightEye.rotation.x = Math.PI / 2;
    rightEye.position.set(0.35, 0, 0);
    const rightLens = new THREE.Mesh(new THREE.CircleGeometry(0.22, 16), lensMat);
    rightLens.position.set(0.35, 0, 0.23);
    eyeGroup.add(rightEye);
    eyeGroup.add(rightLens);

    group.add(eyeGroup);

    // Headlight Spot
    const spot = new THREE.SpotLight(0x00f0ff, 1.8, 12, Math.PI / 6, 0.4);
    spot.position.set(0, 1.0, 0.6);
    spot.target.position.set(0, 0.5, 4);
    group.add(spot);
    group.add(spot.target);

    return group;
  }}

  // Build Procedural EVE 3D Model
  function createEVEMesh() {{
    const group = new THREE.Group();

    // Sleek white ovoid body
    const bodyMat = new THREE.MeshStandardMaterial({{ color: 0xf4f8fd, roughness: 0.15, metalness: 0.1 }});
    const bodyGeo = new THREE.SphereGeometry(0.8, 32, 24);
    bodyGeo.scale(0.8, 1.3, 0.8);
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 1.6;
    body.castShadow = true;
    group.add(body);

    // Floating Head
    const headMat = new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.1 }});
    const headGeo = new THREE.SphereGeometry(0.55, 32, 24);
    headGeo.scale(0.9, 0.9, 0.8);
    const head = new THREE.Mesh(headGeo, headMat);
    head.position.y = 2.6;
    group.add(head);

    // Cyan Visor
    const visorMat = new THREE.MeshBasicMaterial({{ color: 0x00f0ff }});
    const visorGeo = new THREE.SphereGeometry(0.35, 16, 12, 0, Math.PI * 2, 0, Math.PI / 3);
    visorGeo.rotation.x = Math.PI / 2;
    const visor = new THREE.Mesh(visorGeo, visorMat);
    visor.position.set(0, 2.6, 0.35);
    group.add(visor);

    // Thruster Blue Glow Light
    const thrusterLight = new THREE.PointLight(0x00f0ff, 2.0, 5);
    thrusterLight.position.y = 0.8;
    group.add(thrusterLight);

    return group;
  }}

  // Build Procedural World from Config
  function build3DWorld() {{
    // Clear existing meshes
    while(worldGroup.children.length > 0) {{
      worldGroup.remove(worldGroup.children[0]);
    }}
    while(heatmapBarsGroup.children.length > 0) {{
      heatmapBarsGroup.remove(heatmapBarsGroup.children[0]);
    }}
    clueMeshes = [];
    stationMeshes = [];

    const mapCfg = curData.config.map;
    const w = mapCfg.width;
    const h = mapCfg.height;

    // Ground Plane with Grid
    const groundGeo = new THREE.PlaneGeometry(w * 2, h * 2);
    const groundMat = new THREE.MeshStandardMaterial({{ color: 0x0e1424, roughness: 0.9, metalness: 0.1 }});
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(w - 1, 0, h - 1);
    ground.receiveShadow = true;
    worldGroup.add(ground);

    const gridHelper = new THREE.GridHelper(Math.max(w, h) * 2, Math.max(w, h), 0x00f0ff, 0x1b2742);
    gridHelper.position.set(w - 1, 0.01, h - 1);
    worldGroup.add(gridHelper);

    // Obstacles (Scrap heaps)
    const scrapMat = new THREE.MeshStandardMaterial({{ color: 0x3d4758, roughness: 0.8, metalness: 0.4 }});
    mapCfg.obstacles.forEach(([ox, oy]) => {{
      const scrap = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.4, 1.8), scrapMat);
      scrap.position.set(ox * 2, 0.7, oy * 2);
      scrap.castShadow = true;
      scrap.receiveShadow = true;
      worldGroup.add(scrap);
    }});

    // Solar Recharge Stations (Glowing pylons)
    const stationMat = new THREE.MeshStandardMaterial({{ color: 0x00ff88, roughness: 0.3, emissive: 0x00ff88, emissiveIntensity: 0.3 }});
    mapCfg.recharge_stations.forEach(([rx, ry]) => {{
      const stGroup = new THREE.Group();
      stGroup.position.set(rx * 2, 0, ry * 2);

      const base = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.2, 0.3, 16), stationMat);
      base.position.y = 0.15;
      stGroup.add(base);

      const pylon = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.25, 2.0, 8), new THREE.MeshStandardMaterial({{ color: 0xffffff, metalness: 0.8 }}));
      pylon.position.y = 1.0;
      stGroup.add(pylon);

      const sLight = new THREE.PointLight(0x00ff88, 1.5, 6);
      sLight.position.y = 2.2;
      stGroup.add(sLight);

      worldGroup.add(stGroup);
      stationMeshes.push(stGroup);
    }});

    // Clue Holographic Beacons
    const clueMat = new THREE.MeshBasicMaterial({{ color: 0xbf5af2, wireframe: true }});
    mapCfg.clues.forEach(clue => {{
      const cGroup = new THREE.Group();
      cGroup.position.set(clue.x * 2, 1.2, clue.y * 2);

      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.6, 0.08, 12, 24), clueMat);
      ring.rotation.x = Math.PI / 2;
      cGroup.add(ring);

      const cLight = new THREE.PointLight(0xbf5af2, 1.2, 4);
      cGroup.add(cLight);

      worldGroup.add(cGroup);
      clueMeshes.push(cGroup);
    }});

    // Instantiate WALL-E
    walleMesh = createWallEMesh();
    worldGroup.add(walleMesh);

    // Instantiate EVE (hidden until localized or at target)
    eveMesh = createEVEMesh();
    eveMesh.position.set(mapCfg.eve_position[0] * 2, 0, mapCfg.eve_position[1] * 2);
    worldGroup.add(eveMesh);

    // Center camera orbit target
    controls.target.set(w - 1, 0, h - 1);
  }}

  // Update Trajectory Light Ribbon
  function updatePathRibbon(stepIdx) {{
    if (pathLine) worldGroup.remove(pathLine);
    const points = [];
    for (let i = 0; i <= stepIdx && i < curData.traces.length; i++) {{
      const p = curData.traces[i].position;
      points.push(new THREE.Vector3(p[0] * 2, 0.25, p[1] * 2));
    }}
    if (points.length >= 2) {{
      const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
      const lineMat = new THREE.LineBasicMaterial({{ color: 0x00f0ff, linewidth: 3 }});
      pathLine = new THREE.Line(lineGeo, lineMat);
      worldGroup.add(pathLine);
    }}
  }}

  // Update 3D Bayesian Heatmap Elevation Surface
  function update3DHeatmap(stepIdx) {{
    while(heatmapBarsGroup.children.length > 0) {{
      heatmapBarsGroup.remove(heatmapBarsGroup.children[0]);
    }}
    if (!showHeatmap3D || !curData.prob_history || stepIdx >= curData.prob_history.length) return;

    const pMatrix = curData.prob_history[stepIdx];
    const w = curData.config.map.width;
    const h = curData.config.map.height;

    let maxP = 0;
    for(let y = 0; y < h; y++) {{
      for(let x = 0; x < w; x++) {{
        if (pMatrix[y][x] > maxP) maxP = pMatrix[y][x];
      }}
    }}
    if (maxP <= 0.001) return;

    for(let y = 0; y < h; y++) {{
      for(let x = 0; x < w; x++) {{
        const p = pMatrix[y][x];
        if (p > 0.01) {{
          const normH = Math.min(6.0, (p / maxP) * 5.5 + 0.2);
          const barGeo = new THREE.BoxGeometry(1.6, normH, 1.6);
          const alpha = Math.min(0.85, (p / maxP) * 0.8 + 0.15);
          const barMat = new THREE.MeshStandardMaterial({{
            color: p === maxP ? 0xff3366 : 0x00f0ff,
            transparent: true,
            opacity: alpha,
            emissive: p === maxP ? 0xff3366 : 0x00f0ff,
            emissiveIntensity: 0.4
          }});
          const bar = new THREE.Mesh(barGeo, barMat);
          bar.position.set(x * 2, normH / 2, y * 2);
          heatmapBarsGroup.add(bar);
        }}
      }}
    }}
  }}

  // UI Step Synchronization
  function syncStep(stepIdx, triggerAudio = true) {{
    curStep = Math.max(0, Math.min(stepIdx, curData.traces.length - 1));
    document.getElementById('lblStep').innerText = curStep;
    document.getElementById('stepRange').value = curStep;

    const t = curData.traces[curStep];
    if (!t) return;

    // Audio effects
    if (triggerAudio) {{
      if (t.action.startsWith('MOVE')) playBeep(260, 'square', 0.04);
      else if (t.action === 'SCAN') playBeep(620, 'sine', 0.2);
      else if (t.action === 'RECHARGE') playBeep(880, 'triangle', 0.15);
      else if (t.action === 'INSPECT') playBeep(520, 'sawtooth', 0.12);
    }}

    // Update HUD Stats
    document.getElementById('hudMode').innerText = t.agent_mode;
    document.getElementById('hudPos').innerText = '(' + t.position[0] + ', ' + t.position[1] + ')';
    document.getElementById('hudPeak').innerText = '(' + t.belief_peak_coord[0] + ', ' + t.belief_peak_coord[1] + ')';
    document.getElementById('hudEntropy').innerText = t.belief_entropy.toFixed(2) + ' bits';
    document.getElementById('hudConf').innerText = (t.belief_peak_prob * 100).toFixed(1) + '%';
    document.getElementById('hudStatus').innerText = t.inferred_status;
    document.getElementById('hudThought').innerText = t.agent_reasoning;

    // Battery bar
    const bat = t.battery_after;
    document.getElementById('hudBatteryPct').innerText = bat + '%';
    const fill = document.getElementById('hudBatteryFill');
    fill.style.width = bat + '%';
    if (bat < 20) fill.style.background = 'var(--red)';
    else if (bat < 50) fill.style.background = 'var(--yellow)';
    else fill.style.background = 'var(--green)';

    // Update WALL-E Position & Orientation
    if (walleMesh) {{
      const targetX = t.position[0] * 2;
      const targetZ = t.position[1] * 2;
      if (curStep > 0) {{
        const prevP = curData.traces[curStep - 1].position;
        const dx = t.position[0] - prevP[0];
        const dz = t.position[1] - prevP[1];
        if (dx !== 0 || dz !== 0) {{
          walleMesh.rotation.y = Math.atan2(dx, dz);
        }}
      }}
      walleMesh.position.set(targetX, 0, targetZ);
    }}

    // EVE Visibility
    if (eveMesh) {{
      const isRevealed = (t.status_message && t.status_message.includes('EVE located')) || curStep === curData.traces.length - 1;
      eveMesh.visible = isRevealed;
    }}

    updatePathRibbon(curStep);
    update3DHeatmap(curStep);
  }}

  // Switch Mission
  function loadMission(key) {{
    activeMissionKey = key;
    curData = missionsData[key];
    curStep = 0;
    stopPlay();

    document.getElementById('hdrMissionDesc').innerText = curData.name + ' — ' + curData.description;
    const maxS = Math.max(0, curData.traces.length - 1);
    document.getElementById('lblMaxStep').innerText = maxS;
    document.getElementById('stepRange').max = maxS;

    // Stats tab
    const m = curData.metrics;
    document.getElementById('statOutcome').innerText = m.outcome;
    document.getElementById('statSteps').innerText = m.total_steps;
    document.getElementById('statDistance').innerText = m.total_distance_traveled + ' units';
    document.getElementById('statRecharges').innerText = m.recharge_events;
    document.getElementById('statLocError').innerText = (m.localization_error_euclidean !== null ? m.localization_error_euclidean.toFixed(2) + ' tiles' : 'N/A');

    // Clues dossier
    renderCluesDossier();
    build3DWorld();
    syncStep(0, false);
  }}

  function renderCluesDossier() {{
    const container = document.getElementById('cluesListContainer');
    container.innerHTML = '';
    const discovered = curData.traces.filter(t => t.inspected_clue !== null);
    document.getElementById('clueCount').innerText = discovered.length;

    if (discovered.length === 0) {{
      container.innerHTML = '<p style="color: var(--text-dim); font-size: 12px;">No clues inspected yet.</p>';
      return;
    }}

    discovered.forEach(t => {{
      const c = t.inspected_clue;
      const b = document.createElement('div');
      b.className = 'clue-box';
      b.innerHTML = `
        <span class="clue-badge">${{c.type.toUpperCase()}}</span>
        <div style="font-weight: 600; margin: 3px 0;">${{c.description}}</div>
        <div style="color: var(--text-dim); font-size: 11px;">Inspected at (${{c.x}}, ${{c.y}}) on Step ${{t.step_number}}</div>
      `;
      container.appendChild(b);
    }});
  }}

  // Camera Mode Logic
  function setCamMode(mode) {{
    camMode = mode;
    document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
    event.currentTarget.classList.add('active');

    if (mode === 'top') {{
      controls.target.set(curData.config.map.width - 1, 0, curData.config.map.height - 1);
      camera.position.set(curData.config.map.width - 1, 45, curData.config.map.height - 1 + 0.1);
    }} else if (mode === 'orbit') {{
      controls.target.set(curData.config.map.width - 1, 0, curData.config.map.height - 1);
      camera.position.set(20, 26, 32);
    }}
  }}

  // Playback Loop
  function startPlay() {{
    isPlaying = true;
    document.getElementById('btnPlay').innerText = '⏸ Pause';
    const delay = Math.max(40, 350 / speedMultiplier);
    playTimer = setInterval(() => {{
      if (curStep >= curData.traces.length - 1) {{
        stopPlay();
      }} else {{
        syncStep(curStep + 1);
      }}
    }}, delay);
  }}

  function stopPlay() {{
    isPlaying = false;
    document.getElementById('btnPlay').innerText = '▶ Play';
    if (playTimer) clearInterval(playTimer);
  }}

  // Event Listeners
  document.getElementById('btnPlay').addEventListener('click', () => isPlaying ? stopPlay() : startPlay());
  document.getElementById('btnPrev').addEventListener('click', () => syncStep(curStep - 1));
  document.getElementById('btnNext').addEventListener('click', () => syncStep(curStep + 1));
  document.getElementById('btnReset').addEventListener('click', () => {{ stopPlay(); syncStep(0); }});
  document.getElementById('stepRange').addEventListener('input', e => syncStep(parseInt(e.target.value)));

  document.getElementById('btnSpeed').addEventListener('click', () => {{
    const idx = speedOptions.indexOf(speedMultiplier);
    speedMultiplier = speedOptions[(idx + 1) % speedOptions.length];
    document.getElementById('btnSpeed').innerText = speedMultiplier + 'x';
    if (isPlaying) {{ stopPlay(); startPlay(); }}
  }});

  document.getElementById('btnHeatmap').addEventListener('click', () => {{
    showHeatmap3D = !showHeatmap3D;
    document.getElementById('btnHeatmap').classList.toggle('active', showHeatmap3D);
    document.getElementById('btnHeatmap').innerText = '3D Heatmap: ' + (showHeatmap3D ? 'ON' : 'OFF');
    update3DHeatmap(curStep);
  }});

  document.getElementById('btnSound').addEventListener('click', () => {{
    soundEnabled = !soundEnabled;
    document.getElementById('btnSound').innerText = '🔊 Audio: ' + (soundEnabled ? 'ON' : 'OFF');
  }});

  // Mission selector populate
  const selectEl = document.getElementById('missionSelect');
  Object.keys(missionsData).forEach(k => {{
    const opt = document.createElement('option');
    opt.value = k;
    opt.innerText = missionsData[k].name;
    selectEl.appendChild(opt);
  }});
  selectEl.addEventListener('change', e => loadMission(e.target.value));

  // Report Modal
  window.openReportModal = function() {{
    document.getElementById('modalReportPre').innerText = curData.report_markdown;
    document.getElementById('reportModal').style.display = 'flex';
  }};
  window.closeReportModal = function() {{
    document.getElementById('reportModal').style.display = 'none';
  }};

  window.switchSideTab = function(tabName) {{
    document.querySelectorAll('.tab-link').forEach(l => l.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    event.currentTarget.classList.add('active');
    document.getElementById('tab-' + tabName).classList.add('active');
  }};

  // Animation Loop
  let clock = new THREE.Clock();
  function animate() {{
    requestAnimationFrame(animate);
    const elapsedTime = clock.getElapsedTime();

    // Rotate particles
    particles.rotation.y = elapsedTime * 0.02;

    // Animate EVE hover bobbing
    if (eveMesh) {{
      eveMesh.position.y = Math.sin(elapsedTime * 2.5) * 0.2;
    }}

    // Animate Clue Rings
    clueMeshes.forEach((cm, i) => {{
      cm.rotation.y = elapsedTime * 1.5 + i;
      cm.position.y = 1.2 + Math.sin(elapsedTime * 2.0 + i) * 0.15;
    }});

    // Follow camera mode update
    if (camMode === 'follow' && walleMesh) {{
      const offset = new THREE.Vector3(0, 8, 12);
      camera.position.lerp(walleMesh.position.clone().add(offset), 0.08);
      controls.target.lerp(walleMesh.position, 0.08);
    }} else if (camMode === 'first' && walleMesh) {{
      const eyePos = walleMesh.position.clone().add(new THREE.Vector3(0, 1.7, 0.4));
      camera.position.lerp(eyePos, 0.1);
      const lookAtTarget = eyePos.clone().add(new THREE.Vector3(0, -0.2, 8));
      controls.target.lerp(lookAtTarget, 0.1);
    }}

    controls.update();
    renderer.render(scene, camera);
  }}

  window.addEventListener('resize', () => {{
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }});

  // Initial Boot
  loadMission(activeMissionKey);
  animate();
</script>
</body>
</html>"""
        return html

    @classmethod
    def build_and_save(cls, config_paths: List[str], output_path: str):
        """Gather all missions and compile standalone 3D website."""
        bundle = {}
        for p in config_paths:
            base_key = os.path.splitext(os.path.basename(p))[0]
            bundle[base_key] = cls.collect_mission_data(p)

        html = cls.generate_html(bundle)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"🌟 Standalone 3D Website generated successfully at: {output_path}")
