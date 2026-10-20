"""Interactive Live Preview Server for Generated Multi-Stakeholder Applications.

Provides a unified interactive web preview runner for the School Transport System
(Parent Tracking App, Driver Scanner App, School Fleet Admin Console, and DevTools)
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
  <title>{escaped_title} - Interactive Multi-Stakeholder Live Preview</title>
  <style>
    :root {{
      --bg: #090d14;
      --panel: #111827;
      --card: #1f2937;
      --card-hover: #263345;
      --line: #374151;
      --text: #f3f4f6;
      --muted: #9ca3af;
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.2);
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
      --indigo: #6366f1;
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
      backdrop-filter: blur(8px);
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .brand h1 {{
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.3px;
    }}
    .tag {{
      font-size: 11px;
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent);
      border: 1px solid rgba(56, 189, 248, 0.3);
      padding: 2px 8px;
      border-radius: 99px;
      font-weight: 600;
    }}
    .sync-indicator {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      color: var(--success);
      font-weight: 600;
      background: rgba(16, 185, 129, 0.12);
      padding: 3px 9px;
      border-radius: 99px;
    }}
    .sync-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 6px var(--success);
      animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ transform: scale(1); opacity: 1; }}
      50% {{ transform: scale(1.4); opacity: 0.6; }}
    }}
    .nav-tabs {{
      display: flex;
      gap: 6px;
    }}
    .tab-btn {{
      background: transparent;
      border: 1px solid var(--line);
      color: var(--muted);
      padding: 7px 14px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 12px;
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
      box-shadow: 0 0 12px var(--accent-glow);
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
      max-width: 960px;
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
      width: 385px;
      height: 740px;
      background: #000;
      border-radius: 44px;
      border: 8px solid #232c3d;
      box-shadow: 0 25px 60px -10px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.05);
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
      background: #232c3d;
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
      gap: 12px;
    }}

    /* UI Cards */
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      transition: border-color 0.2s;
    }}
    .card:hover {{
      border-color: rgba(56, 189, 248, 0.4);
    }}
    .card-title {{
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .map-sim {{
      height: 180px;
      background: radial-gradient(circle at 50% 50%, #162438 0%, #0d1522 100%);
      border-radius: 12px;
      border: 1px solid var(--line);
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }}
    .map-grid-bg {{
      position: absolute;
      inset: 0;
      background-image: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 20px 20px;
    }}
    .route-path {{
      position: absolute;
      width: 75%;
      height: 3px;
      background: rgba(56, 189, 248, 0.4);
      border-radius: 2px;
    }}
    .bus-icon {{
      font-size: 28px;
      position: relative;
      z-index: 2;
      animation: busBounce 2s infinite alternate ease-in-out;
    }}
    @keyframes busBounce {{
      0% {{ transform: translateY(0) scale(1); }}
      100% {{ transform: translateY(-6px) scale(1.08); }}
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 16px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 12px;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
      width: 100%;
    }}
    .btn-primary {{
      background: var(--accent);
      color: #051424;
    }}
    .btn-primary:hover {{ filter: brightness(1.1); transform: translateY(-1px); }}
    .btn-danger {{
      background: var(--danger);
      color: white;
    }}
    .btn-danger:hover {{ filter: brightness(1.1); }}
    .btn-success {{
      background: var(--success);
      color: #042214;
    }}
    .btn-success:hover {{ filter: brightness(1.1); }}
    .btn-indigo {{
      background: var(--indigo);
      color: white;
    }}
    .btn-indigo:hover {{ filter: brightness(1.1); }}
    .status-badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 99px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.3px;
    }}
    .status-badge.success {{ background: rgba(16, 185, 129, 0.2); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.4); }}
    .status-badge.warning {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid rgba(245, 158, 11, 0.4); }}
    .status-badge.info {{ background: rgba(56, 189, 248, 0.2); color: var(--accent); border: 1px solid rgba(56, 189, 248, 0.4); }}

    /* Admin Grid */
    .admin-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }}
    .table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    .table th, .table td {{
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--line);
    }}
    .table th {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      background: rgba(0, 0, 0, 0.2);
    }}

    /* Toast Notification */
    #toastContainer {{
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .toast {{
      background: #1e293b;
      color: #f8fafc;
      border: 1px solid var(--accent);
      padding: 12px 16px;
      border-radius: 10px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 10px;
      animation: slideIn 0.3s ease;
      max-width: 340px;
    }}
    @keyframes slideIn {{
      from {{ transform: translateX(100%); opacity: 0; }}
      to {{ transform: translateX(0); opacity: 1; }}
    }}

    /* Razorpay Modal */
    .modal-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(4px);
      z-index: 1000;
      justify-content: center;
      align-items: center;
    }}
    .modal-overlay.active {{
      display: flex;
    }}
    .rzp-modal {{
      background: #ffffff;
      color: #0f172a;
      width: 360px;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 25px 50px rgba(0,0,0,0.5);
      animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    @keyframes modalPop {{
      from {{ transform: scale(0.92); opacity: 0; }}
      to {{ transform: scale(1); opacity: 1; }}
    }}
    .rzp-header {{
      background: #0c2340;
      color: white;
      padding: 16px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .rzp-body {{
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .rzp-method-tile {{
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 10px 14px;
      display: flex;
      align-items: center;
      gap: 12px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
      transition: all 0.15s;
    }}
    .rzp-method-tile:hover, .rzp-method-tile.selected {{
      border-color: #0c2340;
      background: #f8fafc;
    }}
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <h1>{escaped_title}</h1>
      <span class="tag">Zero-Cost Monorepo Swarm</span>
      <div class="sync-indicator">
        <span class="sync-dot"></span>
        <span>Firebase Realtime Sync Active</span>
      </div>
    </div>
    <div class="nav-tabs">
      <button class="tab-btn active" onclick="switchTab('parent')">📱 Parent Portal</button>
      <button class="tab-btn" onclick="switchTab('driver')">📷 Driver Console</button>
      <button class="tab-btn" onclick="switchTab('admin')">🖥️ School Admin</button>
      <button class="tab-btn" onclick="switchTab('devtools')">⚡ DevTools & Webhooks</button>
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
              <p style="font-size: 12px; color: var(--muted);" id="parentBoardingDesc">Boarded Bus #4 at Green Glen Residency Stop</p>
              <p style="font-size: 11px; color: var(--accent); margin-top: 4px;" id="parentBoardingMeta">Time: 07:42 AM • Scanned by Driver Ramesh</p>
            </div>

            <div class="map-sim">
              <div class="map-grid-bg"></div>
              <div class="route-path"></div>
              <div class="bus-icon">🚌</div>
              <p style="font-size: 13px; font-weight: 700; margin-top: 8px; z-index: 2;">School Bus Route #4</p>
              <p style="font-size: 11px; color: var(--accent); z-index: 2;" id="busSpeed">Speed: 38 km/h • Live GPS Tracking</p>
            </div>

            <div class="card" style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <p style="font-size: 11px; color: var(--muted)">Estimated Arrival at School</p>
                <p style="font-size: 24px; font-weight: 900; color: var(--success);" id="parentEta">4 mins</p>
              </div>
              <button class="btn btn-primary" style="width: auto; padding: 8px 14px;" onclick="refreshEta()">
                🔄 Refresh ETA
              </button>
            </div>

            <!-- Razorpay Payment Card -->
            <div class="card" id="parentFeeCard">
              <div class="card-title">
                <span>Monthly Transport Fee</span>
                <span style="font-size: 12px; font-weight: 800; color: var(--warning);">₹3,500 / mo</span>
              </div>
              <p style="font-size: 11px; color: var(--muted); margin-bottom: 10px;">Billing cycle: October 2026 • Aarav Sharma</p>
              <button class="btn btn-success" id="btnPayFee" onclick="openRazorpayModal()">
                💳 Pay ₹3,500 via Razorpay
              </button>
            </div>

            <button class="btn btn-danger" id="btnParentSos" onclick="triggerSos('Parent Emergency SOS Alert transmitted to School Police & Ops Desk!')">
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
              <span class="status-badge success">SCANNER ONLINE</span>
            </div>

            <div class="card" style="text-align: center; padding: 18px;">
              <div style="font-size: 38px; margin-bottom: 6px;">📷</div>
              <p style="font-size: 13px; font-weight: 700;">Student QR Badge Scanner</p>
              <p style="font-size: 11px; color: var(--muted); margin-bottom: 12px;">Simulates hardware camera QR badge check-in</p>
              <button class="btn btn-indigo" onclick="simulateQrScan()">
                ⚡ Scan Student Badge (QR)
              </button>
            </div>

            <div class="card">
              <div class="card-title">
                <span>Bus Speed Regulator</span>
                <span id="currentSpeedDisplay" style="font-size: 11px; color: var(--accent);">38 km/h</span>
              </div>
              <div style="display: flex; gap: 6px; margin-top: 4px;">
                <button class="btn btn-primary" style="padding: 6px;" onclick="setBusSpeed(0)">🛑 Stop (0 km/h)</button>
                <button class="btn btn-primary" style="padding: 6px;" onclick="setBusSpeed(38)">🚌 City (38 km/h)</button>
                <button class="btn btn-primary" style="padding: 6px;" onclick="setBusSpeed(55)">⚡ Highway (55 km/h)</button>
              </div>
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

            <button class="btn btn-danger" onclick="triggerSos('Driver SOS Alert: Vehicle breakdown or road hazard on Route #4!')">
              ⚠️ Driver SOS Alert
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- 3. SCHOOL ADMIN OPERATIONS -->
    <section id="pane-admin" class="view-pane">
      <div class="card" style="margin-bottom: 16px;">
        <div class="card-title">
          <span>School Transport Operations Dashboard</span>
          <span class="status-badge success">All 12 Buses Live</span>
        </div>
        <p style="font-size: 12px; color: var(--muted);">Real-time fleet telemetry, Firebase onSnapshot attendance logs, and Razorpay fee settlements.</p>
      </div>

      <div class="admin-grid">
        <div class="card">
          <p style="font-size: 11px; color: var(--muted)">Active Fleet Heartbeats</p>
          <p style="font-size: 28px; font-weight: 900; color: var(--accent);">12 / 12</p>
          <p style="font-size: 11px; color: var(--success); margin-top: 4px;">100% Operational</p>
        </div>
        <div class="card">
          <p style="font-size: 11px; color: var(--muted)">Total Students Boarded</p>
          <p style="font-size: 28px; font-weight: 900; color: var(--success);" id="adminStudentCount">428</p>
          <p style="font-size: 11px; color: var(--muted); margin-top: 4px;">Morning Route</p>
        </div>
        <div class="card">
          <p style="font-size: 11px; color: var(--muted)">Fee Settlements (Razorpay)</p>
          <p style="font-size: 28px; font-weight: 900; color: var(--warning);" id="adminFeePercentage">98.2%</p>
          <p style="font-size: 11px; color: var(--accent); margin-top: 4px;" id="adminFeeTotal">₹4,28,000 Collected</p>
        </div>
        <div class="card">
          <p style="font-size: 11px; color: var(--muted)">Safety Incident Desk</p>
          <p style="font-size: 28px; font-weight: 900; color: var(--success);" id="adminIncidentCount">0 Active</p>
          <p style="font-size: 11px; color: var(--muted); margin-top: 4px;">Zero Open Emergencies</p>
        </div>
      </div>

      <div class="card" style="margin-bottom: 16px;">
        <div class="card-title">Live Route Fleet Status</div>
        <table class="table">
          <thead>
            <tr>
              <th>Route</th>
              <th>Vehicle</th>
              <th>Driver</th>
              <th>Live Speed</th>
              <th>Capacity</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Route #4 (East Ring)</td>
              <td>KA-01-EB-1024</td>
              <td>Ramesh Kumar</td>
              <td id="adminRouteSpeed">38 km/h</td>
              <td>32 / 35</td>
              <td><span class="status-badge success">EN ROUTE</span></td>
            </tr>
            <tr>
              <td>Route #7 (North Valley)</td>
              <td>KA-01-EB-2048</td>
              <td>Suresh Gowda</td>
              <td>42 km/h</td>
              <td>35 / 35</td>
              <td><span class="status-badge warning">FULL</span></td>
            </tr>
            <tr>
              <td>Route #11 (South Campus)</td>
              <td>KA-05-AB-9921</td>
              <td>Anand Patil</td>
              <td>30 km/h</td>
              <td>28 / 30</td>
              <td><span class="status-badge success">EN ROUTE</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="card-title">Razorpay Transport Fee Settlement Ledger</div>
        <table class="table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Student</th>
              <th>Amount</th>
              <th>Payment Gateway</th>
              <th>HMAC Signature</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="settlementLedgerBody">
            <tr>
              <td><code>order_902144</code></td>
              <td>Diya Patel (Grade 4-B)</td>
              <td>₹3,500</td>
              <td>UPI (GooglePay)</td>
              <td><code style="color: var(--success);">SHA256: 4f18...9a0c ✓</code></td>
              <td><span class="status-badge success">SETTLED</span></td>
            </tr>
            <tr>
              <td><code>order_902143</code></td>
              <td>Kabir Verma (Grade 6-C)</td>
              <td>₹3,500</td>
              <td>Credit Card (HDFC)</td>
              <td><code style="color: var(--success);">SHA256: e82b...3f71 ✓</code></td>
              <td><span class="status-badge success">SETTLED</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 4. DEVTOOLS & WEBHOOKS -->
    <section id="pane-devtools" class="view-pane">
      <div class="card" style="margin-bottom: 16px;">
        <div class="card-title">
          <span>Firebase Firestore & Razorpay Telemetry Hub</span>
          <span class="status-badge info">Developer Mode</span>
        </div>
        <p style="font-size: 12px; color: var(--muted); margin-bottom: 12px;">Inspect synced Firestore document trees and test cloud function HMAC webhook signatures.</p>
        <button class="btn btn-indigo" style="width: auto; padding: 8px 16px;" onclick="simulateCloudFunctionWebhook()">
          ⚡ Simulate Incoming Razorpay Webhook Event
        </button>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
        <div class="card">
          <div class="card-title">Firestore Document: <code>/students/STU-101</code></div>
          <pre id="firestoreStudentJson" style="font-size: 11px; color: #a5f3fc; background: #0b1320; padding: 12px; border-radius: 8px; overflow-x: auto;"></pre>
        </div>
        <div class="card">
          <div class="card-title">Firestore Document: <code>/routes/ROUTE-04</code></div>
          <pre id="firestoreRouteJson" style="font-size: 11px; color: #a5f3fc; background: #0b1320; padding: 12px; border-radius: 8px; overflow-x: auto;"></pre>
        </div>
      </div>
    </section>
  </main>

  <!-- Razorpay Checkout Simulator Modal -->
  <div class="modal-overlay" id="rzpModal">
    <div class="rzp-modal">
      <div class="rzp-header">
        <div>
          <h3 style="font-size: 15px; font-weight: 800;">Razorpay Trusted Gateway</h3>
          <p style="font-size: 11px; opacity: 0.8;">VidyaVahan School Transport Fees</p>
        </div>
        <button onclick="closeRazorpayModal()" style="background: transparent; border: none; color: white; font-size: 20px; cursor: pointer;">&times;</button>
      </div>
      <div class="rzp-body">
        <div style="display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #f1f5f9; pb: 8px;">
          <span style="font-size: 12px; color: #64748b;">Amount Payable</span>
          <span style="font-size: 22px; font-weight: 900; color: #0c2340;">₹3,500.00</span>
        </div>
        <p style="font-size: 11px; color: #64748b;">Select Payment Method:</p>
        <div class="rzp-method-tile selected" onclick="selectRzpMethod(this)">
          <span>📱</span>
          <div>
            <div style="font-size: 12px;">Instant UPI / QR</div>
            <div style="font-size: 10px; color: #64748b;">Google Pay, PhonePe, Paytm</div>
          </div>
        </div>
        <div class="rzp-method-tile" onclick="selectRzpMethod(this)">
          <span>💳</span>
          <div>
            <div style="font-size: 12px;">Credit / Debit Cards</div>
            <div style="font-size: 10px; color: #64748b;">Visa, MasterCard, RuPay</div>
          </div>
        </div>
        <div class="rzp-method-tile" onclick="selectRzpMethod(this)">
          <span>🏦</span>
          <div>
            <div style="font-size: 12px;">Netbanking</div>
            <div style="font-size: 10px; color: #64748b;">All Indian Scheduled Banks</div>
          </div>
        </div>
        <button class="btn btn-success" id="btnRzpSubmit" style="margin-top: 6px; padding: 12px;" onclick="executeRazorpayPayment()">
          Pay ₹3,500 Now (Secure 256-bit SSL)
        </button>
      </div>
    </div>
  </div>

  <div id="toastContainer"></div>

  <script>
    // State Store simulating Firestore Document Collections
    const state = {{
      route: {{
        id: 'ROUTE-04',
        name: 'Route #4 (East Ring)',
        driver: 'Ramesh Kumar',
        vehicle: 'KA-01-EB-1024',
        speed: 38,
        etaMinutes: 4,
        status: 'EN ROUTE'
      }},
      students: [
        {{ id: 'STU-101', name: 'Aarav Sharma', grade: '5-A', boarded: true, stop: 'Green Glen Residency', time: '07:42 AM' }},
        {{ id: 'STU-102', name: 'Diya Patel', grade: '4-B', boarded: true, stop: 'Palm Meadows', time: '07:35 AM' }},
        {{ id: 'STU-103', name: 'Kabir Verma', grade: '6-C', boarded: false, stop: 'Silver Oaks Villa', time: null }},
      ],
      feeSettled: false,
      incidents: 0
    }};

    function showToast(title, desc) {{
      const container = document.getElementById('toastContainer');
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.innerHTML = `<div><strong style="display:block;">${{title}}</strong><span>${{desc}}</span></div>`;
      container.appendChild(toast);
      setTimeout(() => {{
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
      }}, 3500);
    }}

    function syncUI() {{
      // Update Parent View
      const aarav = state.students.find(s => s.id === 'STU-101');
      const badge = document.getElementById('parentBoardedBadge');
      const desc = document.getElementById('parentBoardingDesc');
      const meta = document.getElementById('parentBoardingMeta');

      if (aarav.boarded) {{
        badge.className = 'status-badge success';
        badge.innerText = 'STUDENT BOARDED';
        desc.innerText = `Boarded Bus #4 at ${{aarav.stop}} Stop`;
        meta.innerText = `Time: ${{aarav.time || '07:42 AM'}} • Scanned by Driver ${{state.route.driver}}`;
      }} else {{
        badge.className = 'status-badge warning';
        badge.innerText = 'WAITING AT STOP';
        desc.innerText = `Waiting at ${{aarav.stop}} Stop`;
        meta.innerText = `Scheduled pickup: 07:45 AM • Driver approaching`;
      }}

      document.getElementById('parentEta').innerText = `${{state.route.etaMinutes}} mins`;
      document.getElementById('busSpeed').innerText = `Speed: ${{state.route.speed}} km/h • Live GPS Tracking`;
      document.getElementById('currentSpeedDisplay').innerText = `${{state.route.speed}} km/h`;
      document.getElementById('adminRouteSpeed').innerText = `${{state.route.speed}} km/h`;

      // Update Driver Roster
      const rosterList = document.getElementById('rosterList');
      rosterList.innerHTML = '';
      let boardedCount = 0;

      state.students.forEach(s => {{
        if (s.boarded) boardedCount++;
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.alignItems = 'center';
        row.style.padding = '8px 10px';
        row.style.background = '#111827';
        row.style.borderRadius = '8px';
        row.style.border = '1px solid #1f2937';

        row.innerHTML = `
          <div>
            <strong style="font-size: 12px; display: block;">${{s.name}}</strong>
            <small style="color: var(--muted); font-size: 11px;">${{s.id}} • Grade ${{s.grade}} • ${{s.stop}}</small>
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
            transition: all 0.2s;
          ">
            ${{s.boarded ? '✓ BOARDED' : 'WAITING'}}
          </button>
        `;
        rosterList.appendChild(row);
      }});

      document.getElementById('rosterCount').innerText = `${{boardedCount}} / ${{state.students.length}} Boarded`;
      document.getElementById('adminStudentCount').innerText = 426 + boardedCount;

      // Update DevTools JSON
      document.getElementById('firestoreStudentJson').innerText = JSON.stringify(aarav, null, 2);
      document.getElementById('firestoreRouteJson').innerText = JSON.stringify(state.route, null, 2);
    }}

    function toggleStudent(id) {{
      const st = state.students.find(s => s.id === id);
      if (st) {{
        st.boarded = !st.boarded;
        st.time = st.boarded ? new Date().toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}}) : null;
        syncUI();
        showToast('⚡ Firestore onSnapshot Sync', `${{st.name}} is now marked as ${{st.boarded ? 'BOARDED' : 'WAITING'}}`);
      }}
    }}

    function simulateQrScan() {{
      const waiting = state.students.find(s => !s.boarded);
      if (waiting) {{
        waiting.boarded = true;
        waiting.time = new Date().toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}});
        syncUI();
        showToast('📷 QR Badge Verified!', `Scanned: ${{waiting.name}} (${{waiting.id}})\nStatus: BOARDED on Bus #4`);
      }} else {{
        showToast('ℹ️ Roster Complete', 'All enrolled students are already boarded.');
      }}
    }}

    function setBusSpeed(kmh) {{
      state.route.speed = kmh;
      if (kmh === 0) {{
        state.route.etaMinutes = 12;
      }} else if (kmh > 40) {{
        state.route.etaMinutes = 2;
      }} else {{
        state.route.etaMinutes = 4;
      }}
      syncUI();
      showToast('🚌 GPS Speed Regulated', `Bus #4 speed updated to ${{kmh}} km/h. ETA recalibrated.`);
    }}

    function refreshEta() {{
      state.route.etaMinutes = Math.max(1, state.route.etaMinutes - 1);
      syncUI();
      showToast('🔄 Telemetry Refreshed', `Bus #4 is ${{state.route.etaMinutes}} mins away from Green Glen Residency.`);
    }}

    function triggerSos(msg) {{
      state.incidents++;
      document.getElementById('adminIncidentCount').innerText = `${{state.incidents}} Active`;
      document.getElementById('adminIncidentCount').style.color = 'var(--danger)';
      showToast('🚨 SOS ALERT BROADCAST', msg);
    }}

    function switchTab(tab) {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
      document.querySelector(`button[onclick*="${{tab}}"]`).classList.add('active');
      document.getElementById(`pane-${{tab}}`).classList.add('active');
    }}

    // Razorpay Integration
    function openRazorpayModal() {{
      if (state.feeSettled) {{
        showToast('✓ Fee Already Paid', 'Transport fee receipt #RZP-7749 is already settled.');
        return;
      }}
      document.getElementById('rzpModal').classList.add('active');
    }}

    function closeRazorpayModal() {{
      document.getElementById('rzpModal').classList.remove('active');
    }}

    function selectRzpMethod(elem) {{
      document.querySelectorAll('.rzp-method-tile').forEach(t => t.classList.remove('selected'));
      elem.classList.add('selected');
    }}

    function executeRazorpayPayment() {{
      const btn = document.getElementById('btnRzpSubmit');
      btn.innerText = '⏳ Verifying with Bank Gateway...';
      btn.disabled = true;

      setTimeout(() => {{
        closeRazorpayModal();
        state.feeSettled = true;
        const feeBtn = document.getElementById('btnPayFee');
        feeBtn.innerText = '✓ Paid ₹3,500 (Receipt #RZP-7749)';
        feeBtn.className = 'btn btn-primary';
        feeBtn.style.background = 'rgba(16, 185, 129, 0.2)';
        feeBtn.style.color = '#10b981';
        feeBtn.style.border = '1px solid #10b981';

        // Update Admin stats
        document.getElementById('adminFeePercentage').innerText = '99.1%';
        document.getElementById('adminFeeTotal').innerText = '₹4,31,500 Collected';

        // Append to Admin Ledger
        const ledger = document.getElementById('settlementLedgerBody');
        const newRow = document.createElement('tr');
        newRow.innerHTML = `
          <td><code>order_902145</code></td>
          <td>Aarav Sharma (Grade 5-A)</td>
          <td>₹3,500</td>
          <td>Instant UPI (Verified)</td>
          <td><code style="color: var(--success);">SHA256: d91a...88b2 ✓</code></td>
          <td><span class="status-badge success">SETTLED</span></td>
        `;
        ledger.prepend(newRow);

        showToast('💳 Payment Verified', 'Razorpay Payment ID: pay_live_994218 verified via HMAC SHA256 signature.');
      }}, 1200);
    }}

    function simulateCloudFunctionWebhook() {{
      showToast('☁️ Cloud Function Triggered', 'verifyRazorpayWebhook executed. SHA256 HMAC matched payload signature.');
    }}

    // Init
    syncUI();
  </script>
</body>
</html>
"""
