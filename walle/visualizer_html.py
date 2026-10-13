"""Interactive standalone HTML5/Canvas visualization dashboard generator for WALL-E missions."""

from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

from walle.config import MissionConfig
from walle.logger import StepTrace
from walle.report import MissionMetrics


class HtmlVisualizerGenerator:
    """Generates an interactive, zero-dependency HTML5 dashboard for mission exploration."""

    @staticmethod
    def generate_html(
        config: MissionConfig,
        traces: List[StepTrace],
        metrics: MissionMetrics,
        report_markdown: str,
        probability_history: Optional[List[List[List[float]]]] = None,
        ground_truth: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create complete standalone HTML document."""
        traces_json = json.dumps([t.__dict__ for t in traces])
        config_json = json.dumps(config.to_dict())
        metrics_json = json.dumps(metrics.__dict__)
        gt_json = json.dumps(ground_truth if ground_truth else {})
        prob_history_json = json.dumps(probability_history if probability_history else [])
        report_md_escaped = json.dumps(report_markdown)

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WALL-E & EVE Mission Operations Dashboard</title>
<style>
  :root {{
    --bg-dark: #0b0f19;
    --bg-card: #151d30;
    --bg-panel: #111726;
    --border: #232f48;
    --accent-cyan: #00f0ff;
    --accent-yellow: #ffd000;
    --accent-green: #00ff88;
    --accent-red: #ff3366;
    --text-primary: #e6edfa;
    --text-muted: #8a99b5;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }}
  body {{ background: var(--bg-dark); color: var(--text-primary); display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}
  
  /* Top Nav */
  header {{ background: var(--bg-panel); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; }}
  .title-group {{ display: flex; align-items: center; gap: 12px; }}
  .logo {{ font-size: 24px; }}
  .badge {{ background: rgba(0,240,255,0.15); color: var(--accent-cyan); border: 1px solid var(--accent-cyan); padding: 3px 8px; border-radius: 4px; font-size: 11px; text-transform: uppercase; font-weight: bold; }}
  .badge.success {{ background: rgba(0,255,136,0.15); color: var(--accent-green); border-color: var(--accent-green); }}
  .badge.failed {{ background: rgba(255,51,102,0.15); color: var(--accent-red); border-color: var(--accent-red); }}

  /* Main Layout */
  .main-container {{ display: flex; flex: 1; overflow: hidden; }}
  
  /* Left / Canvas Area */
  .viewport-area {{ flex: 1.3; display: flex; flex-direction: column; padding: 16px; border-right: 1px solid var(--border); }}
  .canvas-container {{ flex: 1; display: flex; justify-content: center; align-items: center; background: #080b12; border: 1px solid var(--border); border-radius: 8px; position: relative; overflow: hidden; }}
  canvas {{ box-shadow: 0 0 20px rgba(0,0,0,0.5); border-radius: 4px; }}

  /* Controls */
  .control-bar {{ margin-top: 12px; background: var(--bg-card); padding: 12px 16px; border-radius: 8px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }}
  .slider-row {{ display: flex; align-items: center; gap: 12px; }}
  .slider-row input[type=range] {{ flex: 1; accent-color: var(--accent-cyan); height: 6px; cursor: pointer; }}
  .btn-row {{ display: flex; justify-content: space-between; align-items: center; }}
  .btn-group {{ display: flex; gap: 8px; }}
  button {{ background: var(--bg-panel); color: var(--text-primary); border: 1px solid var(--border); padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; }}
  button:hover {{ border-color: var(--accent-cyan); color: var(--accent-cyan); }}
  button.active {{ background: rgba(0,240,255,0.2); border-color: var(--accent-cyan); color: var(--accent-cyan); }}
  
  /* Right / Telemetry & Dossier */
  .telemetry-area {{ flex: 1; display: flex; flex-direction: column; overflow-y: auto; background: var(--bg-dark); }}
  .tabs {{ display: flex; border-bottom: 1px solid var(--border); background: var(--bg-panel); }}
  .tab-btn {{ flex: 1; padding: 12px; border: none; border-radius: 0; background: transparent; text-align: center; font-size: 13px; border-bottom: 2px solid transparent; color: var(--text-muted); }}
  .tab-btn.active {{ color: var(--accent-cyan); border-bottom-color: var(--accent-cyan); background: rgba(0,240,255,0.05); }}
  
  .tab-content {{ padding: 16px; flex: 1; overflow-y: auto; display: none; }}
  .tab-content.active {{ display: block; }}

  /* Telemetry Cards */
  .metric-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 16px; }}
  .metric-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 12px; }}
  .metric-title {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px; }}
  .metric-val {{ font-size: 18px; font-weight: bold; color: var(--accent-cyan); }}
  
  /* Battery Meter */
  .battery-container {{ margin: 12px 0; }}
  .battery-bar-bg {{ background: #080b12; height: 12px; border-radius: 6px; overflow: hidden; border: 1px solid var(--border); }}
  .battery-fill {{ height: 100%; width: 100%; background: var(--accent-green); transition: width 0.3s; }}
  
  .reasoning-box {{ background: rgba(0,240,255,0.05); border-left: 3px solid var(--accent-cyan); padding: 12px; border-radius: 4px; margin-top: 12px; font-size: 13px; line-height: 1.5; }}
  .clue-item {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 12px; margin-bottom: 8px; }}
  .clue-badge {{ font-size: 10px; background: rgba(255,208,0,0.15); color: var(--accent-yellow); padding: 2px 6px; border-radius: 3px; font-weight: bold; display: inline-block; margin-bottom: 4px; }}

  /* Legend */
  .legend {{ display: flex; gap: 12px; font-size: 11px; margin-top: 6px; flex-wrap: wrap; }}
  .legend-item {{ display: flex; align-items: center; gap: 4px; }}
  .legend-box {{ width: 10px; height: 10px; border-radius: 2px; }}
  
  pre {{ background: #080b12; padding: 16px; border-radius: 6px; border: 1px solid var(--border); font-size: 12px; overflow-x: auto; white-space: pre-wrap; }}
</style>
</head>
<body>

<header>
  <div class="title-group">
    <div class="logo">🤖</div>
    <div>
      <h2 style="font-size: 16px; font-weight: 600;">{config.name}</h2>
      <p style="font-size: 12px; color: var(--text-muted);">{config.description}</p>
    </div>
  </div>
  <div>
    <span class="badge {'success' if 'SUCCESS' in metrics.outcome else 'failed'}">{metrics.outcome}</span>
  </div>
</header>

<div class="main-container">
  <!-- Viewport Canvas Area -->
  <div class="viewport-area">
    <div class="canvas-container">
      <canvas id="gridCanvas" width="600" height="600"></canvas>
    </div>

    <!-- Controls -->
    <div class="control-bar">
      <div class="slider-row">
        <span style="font-size: 12px; font-weight: bold; width: 60px;">STEP <span id="currentStepText">0</span></span>
        <input type="range" id="stepSlider" min="0" max="{max(0, len(traces) - 1)}" value="0">
        <span style="font-size: 12px; color: var(--text-muted); width: 40px; text-align: right;">/ {max(0, len(traces) - 1)}</span>
      </div>

      <div class="btn-row">
        <div class="btn-group">
          <button id="btnPrev">◀ Prev</button>
          <button id="btnPlay">▶ Play</button>
          <button id="btnNext">Next ▶</button>
          <button id="btnReset">Reset</button>
        </div>
        <div class="btn-group">
          <button id="btnHeatmap" class="active">Heatmap: ON</button>
          <button id="btnSpeed">1x</button>
        </div>
      </div>

      <div class="legend">
        <div class="legend-item"><div class="legend-box" style="background:#ffd000;"></div> WALL-E</div>
        <div class="legend-item"><div class="legend-box" style="background:#00ff88;"></div> Solar Station</div>
        <div class="legend-item"><div class="legend-box" style="background:#3a4b6e;"></div> Scrap Pile</div>
        <div class="legend-item"><div class="legend-box" style="background:#ff3366;"></div> EVE Peak Target</div>
        <div class="legend-item"><div class="legend-box" style="background:#a855f7;"></div> Clue Beacon</div>
      </div>
    </div>
  </div>

  <!-- Telemetry & Intel Area -->
  <div class="telemetry-area">
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('telemetry')">Live Telemetry</button>
      <button class="tab-btn" onclick="switchTab('clues')">Dossier ({metrics.clues_found})</button>
      <button class="tab-btn" onclick="switchTab('report')">Mission Report</button>
    </div>

    <!-- Live Telemetry Tab -->
    <div id="tab-telemetry" class="tab-content active">
      <div class="metric-grid">
        <div class="metric-card">
          <div class="metric-title">Agent Mode</div>
          <div class="metric-val" id="valMode" style="font-size: 15px;">EXPLORATION</div>
        </div>
        <div class="metric-card">
          <div class="metric-title">Last Action</div>
          <div class="metric-val" id="valAction" style="color: var(--accent-yellow); font-size: 15px;">-</div>
        </div>
        <div class="metric-card">
          <div class="metric-title">WALL-E Position</div>
          <div class="metric-val" id="valPos">(0, 0)</div>
        </div>
        <div class="metric-card">
          <div class="metric-title">Peak Coordinate</div>
          <div class="metric-val" id="valPeak" style="color: var(--accent-red);">(0, 0)</div>
        </div>
        <div class="metric-card">
          <div class="metric-title">Shannon Entropy</div>
          <div class="metric-val" id="valEntropy">0.00 bits</div>
        </div>
        <div class="metric-card">
          <div class="metric-title">Peak Confidence</div>
          <div class="metric-val" id="valConfidence">0.0%</div>
        </div>
      </div>

      <div class="battery-container">
        <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
          <span>BATTERY CHARGE</span>
          <span id="valBatteryText" style="font-weight: bold; color: var(--accent-green);">100%</span>
        </div>
        <div class="battery-bar-bg">
          <div id="batteryFill" class="battery-fill"></div>
        </div>
      </div>

      <div class="metric-card" style="margin-top: 12px;">
        <div class="metric-title">Inferred EVE Status</div>
        <div class="metric-val" id="valStatus" style="font-size: 14px; color: var(--accent-cyan);">{metrics.inferred_status}</div>
      </div>

      <div class="reasoning-box">
        <div style="font-size: 11px; text-transform: uppercase; color: var(--accent-cyan); margin-bottom: 4px; font-weight: bold;">Tactical Rationale</div>
        <div id="valReasoning">Awaiting first step...</div>
      </div>
    </div>

    <!-- Clues Dossier Tab -->
    <div id="tab-clues" class="tab-content">
      <div id="cluesList">
        <!-- Rendered via JS -->
      </div>
    </div>

    <!-- Report Tab -->
    <div id="tab-report" class="tab-content">
      <pre id="reportMarkdownText"></pre>
    </div>
  </div>
</div>

<script>
  // Mission Data
  const traces = {traces_json};
  const config = {config_json};
  const metrics = {metrics_json};
  const groundTruth = {gt_json};
  const probHistory = {prob_history_json};
  const reportMarkdown = {report_md_escaped};

  // State
  let currentStepIdx = 0;
  let isPlaying = false;
  let playInterval = null;
  let showHeatmap = true;
  let playbackSpeed = 1; // 1x, 2x, 5x
  const speeds = [1, 2, 5];

  // DOM Elements
  const canvas = document.getElementById("gridCanvas");
  const ctx = canvas.getContext("2d");
  const slider = document.getElementById("stepSlider");
  const stepText = document.getElementById("currentStepText");
  const btnPlay = document.getElementById("btnPlay");
  const btnPrev = document.getElementById("btnPrev");
  const btnNext = document.getElementById("btnNext");
  const btnReset = document.getElementById("btnReset");
  const btnHeatmap = document.getElementById("btnHeatmap");
  const btnSpeed = document.getElementById("btnSpeed");

  // Grid dimensions
  const mapW = config.map.width;
  const mapH = config.map.height;
  const cellSize = Math.floor(Math.min(canvas.width / mapW, canvas.height / mapH));
  canvas.width = cellSize * mapW;
  canvas.height = cellSize * mapH;

  function init() {{
    document.getElementById("reportMarkdownText").innerText = reportMarkdown;
    renderCluesDossier();
    updateUI(0);
  }}

  function updateUI(stepIdx) {{
    currentStepIdx = Math.max(0, Math.min(stepIdx, traces.length - 1));
    slider.value = currentStepIdx;
    stepText.innerText = currentStepIdx;

    if (traces.length === 0) return;
    const t = traces[currentStepIdx];

    // Update Telemetry
    document.getElementById("valMode").innerText = t.agent_mode;
    document.getElementById("valAction").innerText = t.action + (t.action_cost ? " (-" + t.action_cost + ")" : "");
    document.getElementById("valPos").innerText = "(" + t.position[0] + ", " + t.position[1] + ")";
    document.getElementById("valPeak").innerText = "(" + t.belief_peak_coord[0] + ", " + t.belief_peak_coord[1] + ")";
    document.getElementById("valEntropy").innerText = t.belief_entropy.toFixed(2) + " bits";
    document.getElementById("valConfidence").innerText = (t.belief_peak_prob * 100).toFixed(1) + "%";
    document.getElementById("valStatus").innerText = t.inferred_status;
    document.getElementById("valReasoning").innerText = t.agent_reasoning;

    // Battery
    const batPct = Math.max(0, Math.min(100, t.battery_after));
    document.getElementById("valBatteryText").innerText = batPct + "%";
    const fillEl = document.getElementById("batteryFill");
    fillEl.style.width = batPct + "%";
    if (batPct < 20) fillEl.style.background = "var(--accent-red)";
    else if (batPct < 50) fillEl.style.background = "var(--accent-yellow)";
    else fillEl.style.background = "var(--accent-green)";

    drawMap(t);
  }}

  function drawMap(currentTrace) {{
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. Draw Grid Background
    for (let y = 0; y < mapH; y++) {{
      for (let x = 0; x < mapW; x++) {{
        ctx.strokeStyle = "#172033";
        ctx.strokeRect(x * cellSize, y * cellSize, cellSize, cellSize);
      }}
    }}

    // 2. Obstacles
    config.map.obstacles.forEach(([ox, oy]) => {{
      ctx.fillStyle = "#27344e";
      ctx.fillRect(ox * cellSize + 2, oy * cellSize + 2, cellSize - 4, cellSize - 4);
      // Scrap texture lines
      ctx.strokeStyle = "#1b2438";
      ctx.beginPath();
      ctx.moveTo(ox * cellSize + 4, oy * cellSize + cellSize - 4);
      ctx.lineTo(ox * cellSize + cellSize - 4, oy * cellSize + 4);
      ctx.stroke();
    }});

    // 3. Recharge Stations
    config.map.recharge_stations.forEach(([rx, ry]) => {{
      ctx.fillStyle = "rgba(0, 255, 136, 0.2)";
      ctx.fillRect(rx * cellSize, ry * cellSize, cellSize, cellSize);
      ctx.fillStyle = "#00ff88";
      ctx.font = `${{Math.floor(cellSize * 0.6)}}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⚡", (rx + 0.5) * cellSize, (ry + 0.5) * cellSize);
    }});

    // 4. Clue Markers
    config.map.clues.forEach(clue => {{
      ctx.fillStyle = "rgba(168, 85, 247, 0.25)";
      ctx.fillRect(clue.x * cellSize, clue.y * cellSize, cellSize, cellSize);
      ctx.fillStyle = "#a855f7";
      ctx.font = `bold ${{Math.floor(cellSize * 0.5)}}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("?", (clue.x + 0.5) * cellSize, (clue.y + 0.5) * cellSize);
    }});

    // 5. Probability Heatmap Overlay
    if (showHeatmap && probHistory.length > currentStepIdx) {{
      const pGrid = probHistory[currentStepIdx];
      let maxP = 0;
      for (let y = 0; y < mapH; y++) {{
        for (let x = 0; x < mapW; x++) {{
          if (pGrid[y][x] > maxP) maxP = pGrid[y][x];
        }}
      }}
      if (maxP > 0) {{
        for (let y = 0; y < mapH; y++) {{
          for (let x = 0; x < mapW; x++) {{
            const p = pGrid[y][x];
            if (p > 0.005) {{
              const alpha = Math.min(0.65, (p / maxP) * 0.7);
              ctx.fillStyle = `rgba(255, 51, 102, ${{alpha}})`;
              ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
            }}
          }}
        }}
      }}
    }}

    // 6. Visited Path Breadcrumbs
    ctx.strokeStyle = "rgba(0, 240, 255, 0.5)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i <= currentStepIdx; i++) {{
      const p = traces[i].position;
      const px = (p[0] + 0.5) * cellSize;
      const py = (p[1] + 0.5) * cellSize;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }}
    ctx.stroke();

    // 7. WALL-E Avatar
    const wx = (currentTrace.position[0] + 0.5) * cellSize;
    const wy = (currentTrace.position[1] + 0.5) * cellSize;

    // Outer glow
    ctx.beginPath();
    ctx.arc(wx, wy, cellSize * 0.45, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255, 208, 0, 0.3)";
    ctx.fill();

    ctx.font = `${{Math.floor(cellSize * 0.7)}}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("🤖", wx, wy);

    // If EVE is discovered or at final step
    if (currentTrace.status_message && currentTrace.status_message.includes("EVE located")) {{
      const ex = (config.map.eve_position[0] + 0.5) * cellSize;
      const ey = (config.map.eve_position[1] + 0.5) * cellSize;
      ctx.font = `${{Math.floor(cellSize * 0.8)}}px sans-serif`;
      ctx.fillText("🤍", ex, ey);
    }}
  }}

  function renderCluesDossier() {{
    const container = document.getElementById("cluesList");
    container.innerHTML = "";

    const discovered = traces.filter(t => t.inspected_clue !== null);
    if (discovered.length === 0) {{
      container.innerHTML = "<p style='color: var(--text-muted); font-size: 13px;'>No clues have been deciphered yet.</p>";
      return;
    }}

    discovered.forEach(t => {{
      const c = t.inspected_clue;
      const item = document.createElement("div");
      item.className = "clue-item";
      item.innerHTML = `
        <div><span class="clue-badge">${{c.type.toUpperCase()}}</span> <span style="font-size: 11px; color: var(--text-muted);">Step ${{t.step_number}}</span></div>
        <div style="font-weight: 500; font-size: 13px; margin: 4px 0;">${{c.description}}</div>
        <div style="font-size: 11px; color: var(--text-muted);">Coordinates: (${{c.x}}, ${{c.y}})</div>
      `;
      container.appendChild(item);
    }});
  }}

  // Event Listeners
  slider.addEventListener("input", e => updateUI(parseInt(e.target.value)));
  btnPrev.addEventListener("click", () => updateUI(currentStepIdx - 1));
  btnNext.addEventListener("click", () => updateUI(currentStepIdx + 1));
  btnReset.addEventListener("click", () => {{ stopPlaying(); updateUI(0); }});

  btnPlay.addEventListener("click", () => {{
    if (isPlaying) stopPlaying();
    else startPlaying();
  }});

  function startPlaying() {{
    isPlaying = true;
    btnPlay.innerText = "⏸ Pause";
    const delay = Math.max(50, 400 / playbackSpeed);
    playInterval = setInterval(() => {{
      if (currentStepIdx >= traces.length - 1) {{
        stopPlaying();
      }} else {{
        updateUI(currentStepIdx + 1);
      }}
    }}, delay);
  }}

  function stopPlaying() {{
    isPlaying = false;
    btnPlay.innerText = "▶ Play";
    if (playInterval) clearInterval(playInterval);
  }}

  btnSpeed.addEventListener("click", () => {{
    const curIdx = speeds.indexOf(playbackSpeed);
    playbackSpeed = speeds[(curIdx + 1) % speeds.length];
    btnSpeed.innerText = playbackSpeed + "x";
    if (isPlaying) {{
      stopPlaying();
      startPlaying();
    }}
  }});

  btnHeatmap.addEventListener("click", () => {{
    showHeatmap = !showHeatmap;
    btnHeatmap.classList.toggle("active", showHeatmap);
    btnHeatmap.innerText = "Heatmap: " + (showHeatmap ? "ON" : "OFF");
    updateUI(currentStepIdx);
  }});

  window.switchTab = function(tabName) {{
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    event.currentTarget.classList.add("active");
    document.getElementById("tab-" + tabName).classList.add("active");
  }};

  init();
</script>
</body>
</html>"""
        return html_template

    @classmethod
    def save_dashboard(
        cls,
        output_path: str,
        config: MissionConfig,
        traces: List[StepTrace],
        metrics: MissionMetrics,
        report_markdown: str,
        probability_history: Optional[List[List[List[float]]]] = None,
        ground_truth: Optional[Dict[str, Any]] = None,
    ):
        """Write visualizer dashboard to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        html = cls.generate_html(
            config=config,
            traces=traces,
            metrics=metrics,
            report_markdown=report_markdown,
            probability_history=probability_history,
            ground_truth=ground_truth,
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
