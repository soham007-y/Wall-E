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
    """Generates a complete, high-visibility interactive 3D WebGL website using Three.js."""

    @staticmethod
    def collect_mission_data(config_path: str) -> Dict[str, Any]:
        """Run mission to gather full 3D trace data including probability matrices."""
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
        """Render complete 3D WebGL website HTML with local vendor scripts and CDN fallbacks."""
        bundle_json = json.dumps(missions_bundle)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WALL-E & EVE 3D Tactical Holodeck</title>
<!-- Local Vendor Scripts with CDN Fallbacks for 100% offline & online compatibility -->
<script src="vendor/three.min.js"></script>
<script>
  if (typeof THREE === 'undefined') {{
    document.write('<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"><\\/script>');
  }}
</script>
<script src="vendor/OrbitControls.js"></script>
<script>
  if (typeof THREE !== 'undefined' && typeof THREE.OrbitControls === 'undefined') {{
    document.write('<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"><\\/script>');
  }}
</script>

<style>
  :root {{
    --bg-dark: #0a0f1d;
    --panel-bg: rgba(13, 20, 36, 0.88);
    --panel-border: rgba(0, 240, 255, 0.35);
    --cyan: #00f0ff;
    --yellow: #ffd000;
    --green: #00ff88;
    --red: #ff3366;
    --purple: #bf5af2;
    --text: #e6edfa;
    --text-dim: #94a3b8;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }}
  body, html {{ width: 100%; height: 100%; overflow: hidden; background: var(--bg-dark); color: var(--text); }}
  
  #canvas3d {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; display: block; z-index: 1; }}

  /* Top Navigation */
  .top-bar {{
    position: absolute; top: 0; left: 0; right: 0;
    padding: 14px 24px;
    display: flex; justify-content: space-between; align-items: center;
    background: linear-gradient(180deg, rgba(10, 15, 29, 0.95) 0%, rgba(10, 15, 29, 0.4) 80%, transparent 100%);
    pointer-events: none;
    z-index: 10;
  }}
  .brand {{ display: flex; align-items: center; gap: 12px; pointer-events: auto; }}
  .logo {{ font-size: 30px; filter: drop-shadow(0 0 10px rgba(255, 208, 0, 0.6)); }}
  .title-h1 {{ font-size: 19px; font-weight: 700; letter-spacing: 1px; color: #fff; }}
  .title-sub {{ font-size: 12px; color: var(--cyan); letter-spacing: 0.5px; }}

  .nav-right {{ pointer-events: auto; display: flex; align-items: center; gap: 12px; }}
  select {{
    background: var(--panel-bg); color: var(--cyan);
    border: 1px solid var(--panel-border); border-radius: 6px;
    padding: 8px 14px; font-size: 13px; font-weight: 600;
    outline: none; cursor: pointer; backdrop-filter: blur(8px);
  }}
  .badge-link {{
    background: rgba(0, 240, 255, 0.15); color: var(--cyan);
    border: 1px solid var(--cyan); border-radius: 6px;
    padding: 7px 12px; font-size: 12px; font-weight: 600;
    text-decoration: none; transition: all 0.2s;
  }}
  .badge-link:hover {{ background: rgba(0, 240, 255, 0.3); box-shadow: 0 0 10px rgba(0, 240, 255, 0.5); }}

  /* Camera Mode Bar */
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
  .pill-btn.active {{ background: rgba(0, 240, 255, 0.25); color: var(--cyan); border-color: var(--cyan); font-weight: 600; box-shadow: 0 0 12px rgba(0, 240, 255, 0.4); }}

  /* Left Intel HUD Card */
  .intel-hud {{
    position: absolute; top: 120px; left: 24px; width: 310px;
    background: var(--panel-bg); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 16px;
    backdrop-filter: blur(12px); box-shadow: 0 8px 24px rgba(0,0,0,0.6);
    z-index: 10; display: flex; flex-direction: column; gap: 12px;
  }}
  .hud-title {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--cyan); font-weight: 700; }}
  .stat-row {{ display: flex; justify-content: space-between; align-items: center; font-size: 13px; }}
  .stat-label {{ color: var(--text-dim); }}
  .stat-val {{ font-weight: 700; color: #fff; }}

  /* Battery Meter */
  .battery-bar {{ width: 100%; height: 10px; background: rgba(0,0,0,0.5); border-radius: 5px; overflow: hidden; border: 1px solid rgba(255,255,255,0.15); margin-top: 4px; }}
  .battery-fill {{ height: 100%; width: 100%; background: var(--green); transition: width 0.3s; }}

  /* Thought bubble / Rationale */
  .thought-card {{
    background: rgba(0, 240, 255, 0.08); border-left: 3px solid var(--cyan);
    padding: 10px; border-radius: 4px; font-size: 12px; line-height: 1.5; color: #e2e8f0;
  }}

  /* Right Side Intel Drawer */
  .side-panel {{
    position: absolute; top: 80px; right: 24px; width: 330px; max-height: calc(100vh - 120px);
    background: var(--panel-bg); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 16px; overflow-y: auto;
    backdrop-filter: blur(12px); box-shadow: 0 8px 24px rgba(0,0,0,0.6);
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

  .clue-badge {{ display: inline-block; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 3px; background: rgba(191, 90, 242, 0.25); color: var(--purple); border: 1px solid var(--purple); margin-bottom: 4px; }}
  .clue-box {{ background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 10px; margin-bottom: 8px; font-size: 12px; }}

  /* Bottom Playback Control Deck */
  .control-deck {{
    position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
    width: min(900px, calc(100% - 40px));
    background: var(--panel-bg); border: 1px solid var(--panel-border);
    border-radius: 12px; padding: 14px 20px;
    backdrop-filter: blur(14px); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.7);
    display: flex; flex-direction: column; gap: 10px;
    z-index: 10;
  }}
  .slider-wrapper {{ display: flex; align-items: center; gap: 14px; }}
  .step-label {{ font-size: 13px; font-weight: 700; color: var(--cyan); width: 90px; }}
  input[type=range] {{
    flex: 1; accent-color: var(--cyan); height: 6px; cursor: pointer;
    background: rgba(255, 255, 255, 0.15); border-radius: 3px;
  }}
  .deck-actions {{ display: flex; justify-content: space-between; align-items: center; }}
  .btn-grp {{ display: flex; gap: 8px; }}
  .action-btn {{
    background: rgba(255, 255, 255, 0.08); color: #fff;
    border: 1px solid var(--panel-border); border-radius: 6px;
    padding: 7px 16px; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: all 0.2s;
  }}
  .action-btn:hover {{ border-color: var(--cyan); color: var(--cyan); }}
  .action-btn.active {{ background: rgba(0, 240, 255, 0.25); color: var(--cyan); border-color: var(--cyan); }}

  /* Modal for Full Report */
  .modal-overlay {{
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8);
    backdrop-filter: blur(8px); z-index: 100; justify-content: center; align-items: center;
  }}
  .modal-box {{
    width: min(840px, 92vw); max-height: 85vh; background: #0b1220;
    border: 1px solid var(--cyan); border-radius: 12px; padding: 24px;
    overflow-y: auto; box-shadow: 0 0 50px rgba(0, 240, 255, 0.35); position: relative;
  }}
  .close-btn {{ position: absolute; top: 16px; right: 20px; font-size: 24px; cursor: pointer; color: var(--text-dim); background: none; border: none; }}
  pre {{ white-space: pre-wrap; font-size: 13px; line-height: 1.6; color: #ccd6e6; }}

  /* WebGL Warning Banner */
  #webglError {{
    display: none; position: absolute; inset: 0; background: #080c16; z-index: 999;
    flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 24px;
  }}
</style>
</head>
<body>

<div id="webglError">
  <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
  <h2 style="color: var(--red); margin-bottom: 8px;">WebGL 3D Context Unavailable</h2>
  <p style="color: var(--text-dim); max-width: 500px; margin-bottom: 20px;">Your browser could not initialize WebGL or 3D graphics hardware acceleration. You can view the full 2D interactive tactical dashboard instead:</p>
  <a href="visualizer.html" class="badge-link" style="font-size: 14px; padding: 10px 20px;">Open 2D Tactical Dashboard</a>
</div>

<div class="top-bar">
  <div class="brand">
    <div class="logo">🤖</div>
    <div>
      <div class="title-h1">WALL-E & EVE 3D TACTICAL HOLODECK</div>
      <div class="title-sub" id="hdrMissionDesc">Autonomous Signal Triangulation & Rescue</div>
    </div>
  </div>
  <div class="nav-right">
    <span style="font-size: 12px; color: var(--text-dim); font-weight: bold;">MISSION:</span>
    <select id="missionSelect">
      <!-- Populated via JS -->
    </select>
    <a href="visualizer.html" class="badge-link">🗺️ 2D Dashboard</a>
  </div>
</div>

<!-- Camera Mode Buttons -->
<div class="cam-bar">
  <button class="pill-btn active" id="btnCamOrbit" onclick="setCamMode('orbit')">🎥 Free Orbit</button>
  <button class="pill-btn" id="btnCamFollow" onclick="setCamMode('follow')">🤖 Follow WALL-E</button>
  <button class="pill-btn" id="btnCamTop" onclick="setCamMode('top')">🗺️ Tactical Top-Down</button>
  <button class="pill-btn" id="btnCamFirst" onclick="setCamMode('first')">👁️ WALL-E Lens</button>
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
      <button class="action-btn active" id="btnHoloEve">EVE Holo: ON</button>
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
  let showHoloEve = true;
  let soundEnabled = true;
  let camMode = 'orbit';

  // Web Audio Synthesizer
  let audioCtx = null;
  function getAudioContext() {{
    if (!audioCtx) {{
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) audioCtx = new AudioContextClass();
    }}
    return audioCtx;
  }}

  function playBeep(freq = 440, type = 'sine', duration = 0.08) {{
    if (!soundEnabled) return;
    try {{
      const ctx = getAudioContext();
      if (!ctx) return;
      if (ctx.state === 'suspended') ctx.resume();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + duration);
    }} catch(e) {{}}
  }}

  // Check Three.js availability
  if (typeof THREE === 'undefined') {{
    document.getElementById('webglError').style.display = 'flex';
    throw new Error('Three.js failed to load.');
  }}

  // Three.js Scene Setup
  const canvas = document.getElementById('canvas3d');
  let renderer;
  try {{
    renderer = new THREE.WebGLRenderer({{ canvas, antialias: true, alpha: false }});
  }} catch(e) {{
    document.getElementById('webglError').style.display = 'flex';
    throw e;
  }}

  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a101f);
  scene.fog = new THREE.Fog(0x0a101f, 35, 140);

  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);

  let controls;
  if (typeof THREE.OrbitControls !== 'undefined') {{
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2.05;
  }} else {{
    // Fallback dummy controls
    controls = {{ target: new THREE.Vector3(), update: function() {{}} }};
  }}

  // High-Visibility Lighting
  const ambientLight = new THREE.AmbientLight(0x718096, 1.8);
  scene.add(ambientLight);

  const sunLight = new THREE.DirectionalLight(0xfff7ed, 2.2);
  sunLight.position.set(30, 50, 25);
  sunLight.castShadow = true;
  sunLight.shadow.mapSize.width = 2048;
  sunLight.shadow.mapSize.height = 2048;
  sunLight.shadow.camera.near = 10;
  sunLight.shadow.camera.far = 140;
  sunLight.shadow.camera.left = -35;
  sunLight.shadow.camera.right = 35;
  sunLight.shadow.camera.top = 35;
  sunLight.shadow.camera.bottom = -35;
  scene.add(sunLight);

  const fillLight = new THREE.DirectionalLight(0x38bdf8, 0.9);
  fillLight.position.set(-20, 30, -20);
  scene.add(fillLight);

  // Atmospheric dust particles
  const particleGeo = new THREE.BufferGeometry();
  const particleCount = 350;
  const posArray = new Float32Array(particleCount * 3);
  for(let i = 0; i < particleCount * 3; i += 3) {{
    posArray[i] = (Math.random() - 0.5) * 80;
    posArray[i+1] = Math.random() * 20;
    posArray[i+2] = (Math.random() - 0.5) * 80;
  }}
  particleGeo.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
  const particleMat = new THREE.PointsMaterial({{ size: 0.22, color: 0x38bdf8, transparent: true, opacity: 0.5 }});
  const particles = new THREE.Points(particleGeo, particleMat);
  scene.add(particles);

  // Scene Group Holders
  const worldGroup = new THREE.Group();
  scene.add(worldGroup);

  let walleMesh = null;
  let eveMesh = null;
  let eveHoloMarker = null;
  let heatmapBarsGroup = new THREE.Group();
  scene.add(heatmapBarsGroup);
  let pathLine = null;
  let clueMeshes = [];
  let stationMeshes = [];

  // Procedural WALL-E 3D Model
  function createWallEMesh() {{
    const group = new THREE.Group();

    // Body Chassis (Bright yellow weathered block)
    const bodyMat = new THREE.MeshStandardMaterial({{ color: 0xf59e0b, roughness: 0.4, metalness: 0.2 }});
    const bodyGeo = new THREE.BoxGeometry(1.3, 1.1, 1.3);
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 0.75;
    body.castShadow = true;
    group.add(body);

    // Tread Tracks
    const treadMat = new THREE.MeshStandardMaterial({{ color: 0x1e293b, roughness: 0.9, metalness: 0.1 }});
    const treadGeo = new THREE.BoxGeometry(0.35, 0.75, 1.5);

    const leftTread = new THREE.Mesh(treadGeo, treadMat);
    leftTread.position.set(-0.85, 0.45, 0);
    leftTread.castShadow = true;
    group.add(leftTread);

    const rightTread = new THREE.Mesh(treadGeo, treadMat);
    rightTread.position.set(0.85, 0.45, 0);
    rightTread.castShadow = true;
    group.add(rightTread);

    // Neck
    const neckMat = new THREE.MeshStandardMaterial({{ color: 0x64748b, metalness: 0.8 }});
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.65), neckMat);
    neck.position.set(0, 1.5, 0.1);
    group.add(neck);

    // Binocular Eyes Group
    const eyeGroup = new THREE.Group();
    eyeGroup.position.set(0, 1.85, 0.2);

    const eyeFrameMat = new THREE.MeshStandardMaterial({{ color: 0xd97706, metalness: 0.3 }});
    const lensMat = new THREE.MeshStandardMaterial({{ color: 0x0284c7, roughness: 0.1, emissive: 0x0284c7, emissiveIntensity: 0.5 }});

    // Left Eye
    const leftEye = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.26, 0.5, 16), eyeFrameMat);
    leftEye.rotation.x = Math.PI / 2;
    leftEye.position.set(-0.38, 0, 0);
    const leftLens = new THREE.Mesh(new THREE.CircleGeometry(0.25, 16), lensMat);
    leftLens.position.set(-0.38, 0, 0.26);
    eyeGroup.add(leftEye);
    eyeGroup.add(leftLens);

    // Right Eye
    const rightEye = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.26, 0.5, 16), eyeFrameMat);
    rightEye.rotation.x = Math.PI / 2;
    rightEye.position.set(0.38, 0, 0);
    const rightLens = new THREE.Mesh(new THREE.CircleGeometry(0.25, 16), lensMat);
    rightLens.position.set(0.38, 0, 0.26);
    eyeGroup.add(rightEye);
    eyeGroup.add(rightLens);

    group.add(eyeGroup);

    // Headlight Spot
    const spot = new THREE.SpotLight(0x00f0ff, 2.5, 16, Math.PI / 5, 0.4);
    spot.position.set(0, 1.2, 0.8);
    spot.target.position.set(0, 0.5, 6);
    group.add(spot);
    group.add(spot.target);

    // Floating Overhead Beacon Halo
    const haloMat = new THREE.MeshBasicMaterial({{ color: 0xffd000, wireframe: true }});
    const halo = new THREE.Mesh(new THREE.TorusGeometry(0.6, 0.05, 8, 16), haloMat);
    halo.rotation.x = Math.PI / 2;
    halo.position.y = 2.4;
    group.add(halo);

    return group;
  }}

  // Procedural EVE 3D Model
  function createEVEMesh() {{
    const group = new THREE.Group();

    // Sleek white ovoid body
    const bodyMat = new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.1, metalness: 0.1 }});
    const bodyGeo = new THREE.SphereGeometry(0.9, 32, 24);
    bodyGeo.scale(0.85, 1.35, 0.85);
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 1.8;
    body.castShadow = true;
    group.add(body);

    // Floating Head
    const headMat = new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.1 }});
    const headGeo = new THREE.SphereGeometry(0.6, 32, 24);
    headGeo.scale(0.95, 0.95, 0.85);
    const head = new THREE.Mesh(headGeo, headMat);
    head.position.y = 2.9;
    group.add(head);

    // Cyan Visor Screen
    const visorMat = new THREE.MeshBasicMaterial({{ color: 0x00f0ff }});
    const visorGeo = new THREE.SphereGeometry(0.4, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2.8);
    visorGeo.rotateX(Math.PI / 2);
    const visor = new THREE.Mesh(visorGeo, visorMat);
    visor.position.set(0, 2.9, 0.4);
    group.add(visor);

    // Blue Thruster Light
    const thrusterLight = new THREE.PointLight(0x00f0ff, 2.8, 8);
    thrusterLight.position.y = 0.9;
    group.add(thrusterLight);

    return group;
  }}

  // Build Procedural 3D World
  function build3DWorld() {{
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
    const centerX = (w - 1);
    const centerZ = (h - 1);

    // Ground Plane & Wasteland Tiles
    const groundGeo = new THREE.PlaneGeometry(w * 2 + 6, h * 2 + 6);
    const groundMat = new THREE.MeshStandardMaterial({{ color: 0x151e2e, roughness: 0.85, metalness: 0.15 }});
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(centerX, -0.01, centerZ);
    ground.receiveShadow = true;
    worldGroup.add(ground);

    // Glowing Hologram Grid Helper
    const gridHelper = new THREE.GridHelper(Math.max(w, h) * 2, Math.max(w, h), 0x00f0ff, 0x1e293b);
    gridHelper.position.set(centerX, 0.02, centerZ);
    worldGroup.add(gridHelper);

    // Obstacles (Scrap heaps with rust highlights)
    const scrapMat = new THREE.MeshStandardMaterial({{ color: 0x475569, roughness: 0.7, metalness: 0.4 }});
    mapCfg.obstacles.forEach(([ox, oy]) => {{
      const scrap = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.4, 1.8), scrapMat);
      scrap.position.set(ox * 2, 0.7, oy * 2);
      scrap.castShadow = true;
      scrap.receiveShadow = true;
      worldGroup.add(scrap);
    }});

    // Solar Recharge Stations
    const stationMat = new THREE.MeshStandardMaterial({{ color: 0x00ff88, roughness: 0.2, emissive: 0x00ff88, emissiveIntensity: 0.4 }});
    mapCfg.recharge_stations.forEach(([rx, ry]) => {{
      const stGroup = new THREE.Group();
      stGroup.position.set(rx * 2, 0, ry * 2);

      const base = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.3, 0.35, 16), stationMat);
      base.position.y = 0.18;
      stGroup.add(base);

      const pylon = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.28, 2.4, 8), new THREE.MeshStandardMaterial({{ color: 0xffffff, metalness: 0.8 }}));
      pylon.position.y = 1.2;
      stGroup.add(pylon);

      // Light Pillar
      const sLight = new THREE.PointLight(0x00ff88, 2.2, 8);
      sLight.position.y = 2.6;
      stGroup.add(sLight);

      worldGroup.add(stGroup);
      stationMeshes.push(stGroup);
    }});

    // Clue Holographic Rings
    const clueMat = new THREE.MeshBasicMaterial({{ color: 0xbf5af2, wireframe: true }});
    mapCfg.clues.forEach(clue => {{
      const cGroup = new THREE.Group();
      cGroup.position.set(clue.x * 2, 1.4, clue.y * 2);

      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.65, 0.08, 12, 24), clueMat);
      ring.rotation.x = Math.PI / 2;
      cGroup.add(ring);

      const cLight = new THREE.PointLight(0xbf5af2, 1.8, 6);
      cGroup.add(cLight);

      worldGroup.add(cGroup);
      clueMeshes.push(cGroup);
    }});

    // Instantiate WALL-E
    walleMesh = createWallEMesh();
    worldGroup.add(walleMesh);

    // Instantiate EVE
    eveMesh = createEVEMesh();
    const eveX = mapCfg.eve_position[0] * 2;
    const eveZ = mapCfg.eve_position[1] * 2;
    eveMesh.position.set(eveX, 0, eveZ);
    worldGroup.add(eveMesh);

    // EVE Holographic Marker (So target coordinate is visible in 3D exploration)
    const holoMat = new THREE.MeshBasicMaterial({{ color: 0x00f0ff, wireframe: true, transparent: true, opacity: 0.65 }});
    eveHoloMarker = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 3.2, 16, 1, true), holoMat);
    eveHoloMarker.position.set(eveX, 1.6, eveZ);
    worldGroup.add(eveHoloMarker);

    // Initial Camera Positioning centered on map
    controls.target.set(centerX, 0.5, centerZ);
    camera.position.set(centerX + w * 1.1, Math.max(w, h) * 1.5, centerZ + h * 1.4);
    controls.update();
  }}

  // Update Trajectory Light Ribbon
  function updatePathRibbon(stepIdx) {{
    if (pathLine) worldGroup.remove(pathLine);
    const points = [];
    for (let i = 0; i <= stepIdx && i < curData.traces.length; i++) {{
      const p = curData.traces[i].position;
      points.push(new THREE.Vector3(p[0] * 2, 0.35, p[1] * 2));
    }}
    if (points.length >= 2) {{
      const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
      const lineMat = new THREE.LineBasicMaterial({{ color: 0x00f0ff, linewidth: 4 }});
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
        if (p > 0.008) {{
          const normH = Math.min(6.5, (p / maxP) * 5.5 + 0.3);
          const barGeo = new THREE.BoxGeometry(1.6, normH, 1.6);
          const alpha = Math.min(0.85, (p / maxP) * 0.75 + 0.2);
          const isPeak = (p === maxP);
          const barMat = new THREE.MeshStandardMaterial({{
            color: isPeak ? 0xff3366 : 0x00f0ff,
            transparent: true,
            opacity: alpha,
            emissive: isPeak ? 0xff3366 : 0x00f0ff,
            emissiveIntensity: isPeak ? 0.6 : 0.3
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
      else if (t.action === 'SCAN') playBeep(640, 'sine', 0.2);
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

    // EVE & Marker Visibility
    const isLocated = (t.status_message && t.status_message.includes('EVE located')) || curStep === curData.traces.length - 1;
    if (eveMesh) {{
      eveMesh.visible = isLocated || showHoloEve;
    }}
    if (eveHoloMarker) {{
      eveHoloMarker.visible = showHoloEve && !isLocated;
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
    const btn = document.getElementById('btnCam' + mode.charAt(0).toUpperCase() + mode.slice(1));
    if (btn) btn.classList.add('active');

    const w = curData.config.map.width;
    const h = curData.config.map.height;
    const centerX = (w - 1);
    const centerZ = (h - 1);

    if (mode === 'top') {{
      controls.target.set(centerX, 0, centerZ);
      camera.position.set(centerX, Math.max(w, h) * 2.5, centerZ + 0.1);
    }} else if (mode === 'orbit') {{
      controls.target.set(centerX, 0.5, centerZ);
      camera.position.set(centerX + w * 1.1, Math.max(w, h) * 1.5, centerZ + h * 1.4);
    }}
    controls.update();
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

  document.getElementById('btnHoloEve').addEventListener('click', () => {{
    showHoloEve = !showHoloEve;
    document.getElementById('btnHoloEve').classList.toggle('active', showHoloEve);
    document.getElementById('btnHoloEve').innerText = 'EVE Holo: ' + (showHoloEve ? 'ON' : 'OFF');
    syncStep(curStep, false);
  }});

  document.getElementById('btnSound').addEventListener('click', () => {{
    soundEnabled = !soundEnabled;
    document.getElementById('btnSound').innerText = '🔊 Audio: ' + (soundEnabled ? 'ON' : 'OFF');
  }});

  // Populate Mission Select Dropdown
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
    const btn = event.currentTarget;
    if (btn) btn.classList.add('active');
    document.getElementById('tab-' + tabName).classList.add('active');
  }};

  // Animation Loop
  let clock = new THREE.Clock();
  function animate() {{
    requestAnimationFrame(animate);
    const elapsedTime = clock.getElapsedTime();

    // Rotate dust particles
    particles.rotation.y = elapsedTime * 0.02;

    // Animate EVE hover bobbing & halo
    if (eveMesh) {{
      eveMesh.position.y = Math.sin(elapsedTime * 2.5) * 0.2;
    }}
    if (eveHoloMarker) {{
      eveHoloMarker.rotation.y = elapsedTime * 0.8;
    }}

    // Animate Clue Rings
    clueMeshes.forEach((cm, i) => {{
      cm.rotation.y = elapsedTime * 1.5 + i;
      cm.position.y = 1.4 + Math.sin(elapsedTime * 2.0 + i) * 0.15;
    }});

    // Follow camera mode update
    if (camMode === 'follow' && walleMesh) {{
      const offset = new THREE.Vector3(0, 9, 13);
      camera.position.lerp(walleMesh.position.clone().add(offset), 0.08);
      controls.target.lerp(walleMesh.position, 0.08);
    }} else if (camMode === 'first' && walleMesh) {{
      const eyePos = walleMesh.position.clone().add(new THREE.Vector3(0, 1.85, 0.4));
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

  // Boot Scene
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
