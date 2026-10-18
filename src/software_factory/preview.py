"""Interactive Live Preview Server for Generated Multi-Stakeholder Applications.

Provides a unified interactive web preview runner for the School Transport System
(Parent Tracking App, Driver Scanner App, and School Fleet Admin Console)
and workspace-generated frontends, rendered in real time within the Web Control Room.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def render_preview_bundle(
    archetype: str = "school_transport",
    project_title: str = "VidyaVahan School Transport",
    custom_files: dict[str, str] | None = None,
) -> str:
    """Render a standalone, zero-dependency interactive HTML bundle for live testing."""
    escaped_title = html.escape(project_title)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} - Interactive Live Preview</title>
  <style>
    :root {{
      --bg: #090d14;
      --panel: #111827;
      --card: #1f2937;
      --line: #374151;
      --text: #f3f4f6;
      --muted: #9ca3af;
      --accent: #38bdf8;
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 12px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .brand h1 {{
      font-size: 16px;
      font-weight: 700;
    }}
    .tag {{
      font-size: 11px;
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent);
      padding: 2px 8px;
      border-radius: 99px;
      font-weight: 600;
    }}
    .nav-tabs {{
      display: flex;
      gap: 8px;
    }}
    .tab-btn {{
      background: transparent;
      border: 1px solid var(--line);
      color: var(--muted);
      padding: 6px 14px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
      transition: all 0.2s;
    }}
    .tab-btn:hover {{
      color: var(--text);
      border-color: var(--accent);
    }}
    .tab-btn.active {{
      background: var(--accent);
      color: #04121f;
      border-color: var(--accent);
    }}
    main {{
      flex: 1;
      padding: 24px;
      display: flex;
      justify-content: center;
      align-items: flex-start;
    }}
    .view-pane {{
      display: none;
      width: 100%;
      max-width: 900px;
      animation: fadeIn 0.25s ease;
    }}
    .view-pane.active {{
      display: block;
    }}
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    /* Mobile Frame */
    .phone-wrapper {{
      display: flex;
      justify-content: center;
    }}
    .phone-mockup {{
      width: 375px;
      height: 720px;
      background: #000;
      border-radius: 40px;
      border: 8px solid #2d3748;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      position: relative;
    }}
    .notch {{
      position: absolute;
      top: 0;
      left: 50%;
      transform: translateX(-50%);
      width: 140px;
      height: 22px;
      background: #2d3748;
      border-bottom-left-radius: 14px;
      border-bottom-right-radius: 14px;
      z-index: 50;
    }}
    .phone-screen {{
      flex: 1;
      background: #090e17;
      overflow-y: auto;
      padding: 30px 16px 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}

    /* UI Cards */
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
    }}
    .card-title {{
      font-size: 14px;
      font-weight: 700;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .map-sim {{
      height: 180px;
      background: #0d1522;
      border-radius: 12px;
      border: 1px solid var(--line);
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }}
    .bus-icon {{
      font-size: 32px;
      animation: bounce 1.8s infinite alternate ease-in-out;
    }}
    @keyframes bounce {{
      0% {{ transform: translateY(0) scale(1); }}
      100% {{ transform: translateY(-8px) scale(1.05); }}
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 16px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
      width: 100%;
    }}
    .btn-primary {{
      background: var(--accent);
      color: #051424;
    }}
    .btn-primary:hover {{ filter: brightness(1.1); }}
    .btn-danger {{
      background: var(--danger);
      color: white;
    }}
    .btn-danger:hover {{ filter: brightness(1.1); }}
    .btn-success {{
      background: var(--success);
      color: #042214;
    }}
    .status-badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 99px;
      font-size: 11px;
      font-weight: 700;
    }}
    .status-badge.success {{ background: rgba(16, 185, 129, 0.2); color: var(--success); }}
    .status-badge.warning {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); }}

    /* Admin Grid */
    .admin-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-bottom: 20px;
    }}
    .table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .table th, .table td {{
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid var(--line);
    }}
    .table th {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <h1>{escaped_title}</h1>
      <span class="tag">Zero-Cost Swarm Generated</span>
    </div>
    <div class="nav-tabs">
      <button class="tab-btn active" onclick="switchTab('parent')">📱 Parent App</button>
      <button class="tab-btn" onclick="switchTab('driver')">📷 Driver Console</button>
      <button class="tab-btn" onclick="switchTab('admin')">🖥️ School Admin</button>
    </div>
  </header>

  <main>
    <!-- 1. PARENT TRACKING APP -->
    <section id="pane-parent" class="view-pane active">
      <div class="phone-wrapper">
        <div class="phone-mockup">
          <div class="notch"></div>
          <div class="phone-screen">
            <div class="card-title" style="margin-top: 10px;">
              <span>Parent Portal</span>
              <span class="status-badge success" id="parentBoardedBadge">STUDENT BOARDED</span>
            </div>

            <div class="card">
              <div class="card-title">
                <span>Student: Aarav Sharma</span>
                <span style="font-size: 11px; color: var(--muted)">Grade 5-A</span>
              </div>
              <p style="font-size: 12px; color: var(--muted);">Boarded Bus #4 at Green Glen Residency Stop</p>
              <p style="font-size: 11px; color: var(--accent); margin-top: 4px;">Time: 07:42 AM • Scanned by Driver Ramesh</p>
            </div>

            <div class="map-sim">
              <div class="bus-icon">🚌</div>
              <p style="font-size: 13px; font-weight: 700; margin-top: 6px;">School Bus Route #4</p>
              <p style="font-size: 11px; color: var(--accent);" id="busSpeed">Speed: 38 km/h • Outer Ring Road</p>
            </div>

            <div class="card" style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <p style="font-size: 11px; color: var(--muted)">Estimated Arrival at School</p>
                <p style="font-size: 24px; font-weight: 900; color: var(--success);" id="parentEta">4 mins</p>
              </div>
              <button class="btn btn-primary" style="width: auto; padding: 8px 14px;" onclick="refreshEta()">
                🔄 Refresh
              </button>
            </div>

            <button class="btn btn-danger" id="btnParentSos" onclick="triggerSos('Parent Emergency Dispatch triggered!')">
              🚨 Emergency Alert
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- 2. DRIVER SCANNER APP -->
    <section id="pane-driver" class="view-pane">
      <div class="phone-wrapper">
        <div class="phone-mockup">
          <div class="notch"></div>
          <div class="phone-screen">
            <div class="card-title" style="margin-top: 10px;">
              <span>Driver Console</span>
              <span class="status-badge success">SCANNER READY</span>
            </div>

            <div class="card" style="text-align: center; padding: 20px;">
              <div style="font-size: 40px; margin-bottom: 8px;">📷</div>
              <p style="font-size: 13px; font-weight: 700;">Simulate QR Badge Scan</p>
              <p style="font-size: 11px; color: var(--muted); margin-bottom: 12px;">Tap below to simulate student boarding</p>
              <button class="btn btn-primary" onclick="simulateQrScan()">
                ⚡ Scan Student Badge (QR)
              </button>
            </div>

            <div class="card">
              <div class="card-title">
                <span>Roster (Route #4)</span>
                <span id="rosterCount" style="font-size: 11px; color: var(--accent);">2 / 3 Boarded</span>
              </div>
              <div id="rosterList" style="display: flex; flex-direction: column; gap: 8px;">
                <!-- Injected via JS -->
              </div>
            </div>

            <button class="btn btn-danger" onclick="triggerSos('Driver Emergency Alert broadcasted to Admin!')">
              ⚠️ Driver SOS Alert
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- 3. SCHOOL ADMIN OPERATIONS -->
    <section id="pane-admin" class="view-pane">
      <div class="card" style="margin-bottom: 20px;">
        <div class="card-title">
          <span>School Transport Operations Dashboard</span>
          <span class="status-badge success">All 12 Buses Live</span>
        </div>
        <p style="font-size: 13px; color: var(--muted);">Real-time monitoring, attendance reconciliation, and fee settlements.</p>
      </div>

      <div class="admin-grid">
        <div class="card">
          <p style="font-size: 12px; color: var(--muted)">Active Fleet Heartbeats</p>
          <p style="font-size: 32px; font-weight: 900; color: var(--accent);">12 / 12</p>
          <p style="font-size: 11px; color: var(--success); margin-top: 4px;">100% Operational</p>
        </div>
        <div class="card">
          <p style="font-size: 12px; color: var(--muted)">Total Students Boarded</p>
          <p style="font-size: 32px; font-weight: 900; color: var(--success);" id="adminStudentCount">428</p>
          <p style="font-size: 11px; color: var(--muted); margin-top: 4px;">Morning Route</p>
        </div>
        <div class="card">
          <p style="font-size: 12px; color: var(--muted)">Fee Settlements (Razorpay)</p>
          <p style="font-size: 32px; font-weight: 900; color: var(--warning);">98.2%</p>
          <p style="font-size: 11px; color: var(--accent); margin-top: 4px;">₹4,28,000 Collected</p>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Live Route Fleet Status</div>
        <table class="table">
          <thead>
            <tr>
              <th>Route</th>
              <th>Vehicle</th>
              <th>Driver</th>
              <th>Capacity</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Route #4 (East Ring)</td>
              <td>KA-01-EB-1024</td>
              <td>Ramesh Kumar</td>
              <td>32 / 35</td>
              <td><span class="status-badge success">EN ROUTE</span></td>
            </tr>
            <tr>
              <td>Route #7 (North Valley)</td>
              <td>KA-01-EB-2048</td>
              <td>Suresh Gowda</td>
              <td>35 / 35</td>
              <td><span class="status-badge warning">FULL</span></td>
            </tr>
            <tr>
              <td>Route #11 (South Campus)</td>
              <td>KA-05-AB-9921</td>
              <td>Anand Patil</td>
              <td>28 / 30</td>
              <td><span class="status-badge success">EN ROUTE</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>

  <script>
    const students = [
      {{ id: 'STU-101', name: 'Aarav Sharma', grade: '5-A', boarded: true }},
      {{ id: 'STU-102', name: 'Diya Patel', grade: '4-B', boarded: true }},
      {{ id: 'STU-103', name: 'Kabir Verma', grade: '6-C', boarded: false }},
    ];

    function renderRoster() {{
      const container = document.getElementById('rosterList');
      container.innerHTML = '';
      let boardedCount = 0;

      students.forEach(s => {{
        if (s.boarded) boardedCount++;
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.alignItems = 'center';
        row.style.padding = '8px 10px';
        row.style.background = '#111827';
        row.style.borderRadius = '8px';

        row.innerHTML = `
          <div>
            <strong style="font-size: 12px; display: block;">${{s.name}}</strong>
            <small style="color: var(--muted); font-size: 11px;">${{s.id}} • Grade ${{s.grade}}</small>
          </div>
          <button onclick="toggleStudent('${{s.id}}')" style="
            background: ${{s.boarded ? 'var(--success)' : 'var(--card)'}};
            color: ${{s.boarded ? '#052316' : 'var(--text)'}};
            border: 1px solid var(--line);
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
          ">
            ${{s.boarded ? '✓ BOARDED' : 'WAITING'}}
          </button>
        `;
        container.appendChild(row);
      }});

      document.getElementById('rosterCount').innerText = `${{boardedCount}} / ${{students.length}} Boarded`;
      document.getElementById('adminStudentCount').innerText = 426 + boardedCount;
    }}

    function toggleStudent(id) {{
      const st = students.find(s => s.id === id);
      if (st) {{
        st.boarded = !st.boarded;
        renderRoster();
      }}
    }}

    function simulateQrScan() {{
      const waiting = students.find(s => !s.boarded);
      if (waiting) {{
        waiting.boarded = true;
        renderRoster();
        alert(`📷 QR Code Scanned!\nStudent Verified: ${{waiting.name}} (${{waiting.id}})\nStatus: BOARDED`);
      }} else {{
        alert('All registered students are already marked as BOARDED!');
      }}
    }}

    function triggerSos(msg) {{
      alert('🚨 SOS TRANSMITTED:\n' + msg + '\nGPS Coordinates: 12.9716, 77.5946');
    }}

    function refreshEta() {{
      const eta = Math.floor(Math.random() * 3) + 2;
      document.getElementById('parentEta').innerText = eta + ' mins';
      document.getElementById('busSpeed').innerText = `Speed: ${{30 + Math.floor(Math.random() * 15)}} km/h • Live GPS`;
    }}

    function switchTab(tab) {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
      document.querySelector(`button[onclick*="${{tab}}"]`).classList.add('active');
      document.getElementById(`pane-${{tab}}`).classList.add('active');
    }}

    // Init
    renderRoster();
  </script>
</body>
</html>
"""

