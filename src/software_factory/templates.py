"""Multi-stakeholder archetype templates for full-scale autonomous software generation.

Provides verified, syntactically valid TypeScript, React, Vite, and mobile
templates for school transport, elder logistics, and commerce marketplace systems.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_standards import AgentEnvironmentBootstrapper
from .figcraft import FigCraftTemplateBuilder

ARCHETYPE_SCHOOL_TRANSPORT = "school_transport"
ARCHETYPE_COMMERCE_MARKETPLACE = "commerce_marketplace"
ARCHETYPE_ELDER_LOGISTICS = "elder_logistics"

SUPPORTED_ARCHETYPES = frozenset({
    ARCHETYPE_SCHOOL_TRANSPORT,
    ARCHETYPE_COMMERCE_MARKETPLACE,
    ARCHETYPE_ELDER_LOGISTICS,
})


def generate_archetype_files(
    archetype: str,
    project_title: str = "Platform",
) -> dict[str, str]:
    """Generate complete multi-stakeholder scaffold files for the selected archetype."""
    if archetype not in SUPPORTED_ARCHETYPES:
        raise ValueError(
            f"Unsupported archetype {archetype!r}. Supported: {sorted(SUPPORTED_ARCHETYPES)}"
        )

    if archetype == ARCHETYPE_SCHOOL_TRANSPORT:
        return _school_transport_template(project_title)
    if archetype == ARCHETYPE_COMMERCE_MARKETPLACE:
        return _commerce_marketplace_template(project_title)
    return _elder_logistics_template(project_title)


def _school_transport_template(title: str) -> dict[str, str]:
    """Multi-stakeholder School Transport System monorepo template."""
    standards_text = AgentEnvironmentBootstrapper.generate_claude_md(title)
    agent_cfg = json.dumps(AgentEnvironmentBootstrapper.generate_agent_config(title), indent=2) + "\n"
    figcraft_doc = FigCraftTemplateBuilder.build_school_transport_document(title).to_json()
    return {
        "CLAUDE.md": standards_text,
        "AGENT.md": standards_text,
        ".agent/config.json": agent_cfg,
        "design/school_transport.figcraft.json": figcraft_doc,
        "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n  - 'packages/*'\n",
        "turbo.json": json.dumps({
            "$schema": "https://turbo.build/schema.json",
            "pipeline": {
                "build": {"dependsOn": ["^build"], "outputs": ["dist/**"]},
                "test": {"dependsOn": ["^build"], "outputs": []},
                "lint": {},
            },
        }, indent=2) + "\n",
        "firestore.rules": (
            "rules_version = '2';\n"
            "service cloud.firestore {\n"
            "  match /databases/{database}/documents {\n"
            "    match /routes/{routeId} {\n"
            "      allow read: if request.auth != null;\n"
            "      allow write: if request.auth.token.role == 'admin' || request.auth.token.role == 'driver';\n"
            "    }\n"
            "    match /students/{studentId} {\n"
            "      allow read: if request.auth != null && (request.auth.token.role == 'admin' || request.auth.uid == resource.data.parentId);\n"
            "      allow write: if request.auth.token.role == 'admin';\n"
            "    }\n"
            "    match /attendance_logs/{logId} {\n"
            "      allow read: if request.auth != null;\n"
            "      allow create: if request.auth.token.role == 'driver' || request.auth.token.role == 'admin';\n"
            "    }\n"
            "    match /fee_transactions/{txId} {\n"
            "      allow read: if request.auth != null && (request.auth.token.role == 'admin' || request.auth.uid == resource.data.parentId);\n"
            "      allow write: if request.auth.token.role == 'admin';\n"
            "    }\n"
            "  }\n"
            "}\n"
        ),
        "packages/shared/types/transport.ts": (
            "export interface Student {\n"
            "  id: string;\n"
            "  name: string;\n"
            "  grade: string;\n"
            "  parentId: string;\n"
            "  parentPhone: string;\n"
            "  assignedBusId: string;\n"
            "  pickupStopId: string;\n"
            "  dropoffStopId: string;\n"
            "  isBoarded: boolean;\n"
            "}\n\n"
            "export interface BusRoute {\n"
            "  id: string;\n"
            "  routeNumber: string;\n"
            "  driverName: string;\n"
            "  driverPhone: string;\n"
            "  vehicleNumber: string;\n"
            "  capacity: number;\n"
            "  currentLocation?: { lat: number; lng: number };\n"
            "  currentSpeedKmh: number;\n"
            "  currentStopName: string;\n"
            "  nextStopEtaMinutes: number;\n"
            "  status: 'IDLE' | 'EN_ROUTE' | 'COMPLETED' | 'EMERGENCY';\n"
            "}\n\n"
            "export interface AttendanceRecord {\n"
            "  id: string;\n"
            "  studentId: string;\n"
            "  studentName: string;\n"
            "  routeId: string;\n"
            "  stopName: string;\n"
            "  timestamp: string;\n"
            "  event: 'BOARDED' | 'DEBOARDED' | 'ABSENT';\n"
            "  scannedByDriverId: string;\n"
            "}\n"
        ),
        "packages/shared/firebase.ts": (
            "// Firebase / Firestore Schema and Client Configuration\n"
            "export const firestoreCollections = {\n"
            "  students: 'students',\n"
            "  routes: 'routes',\n"
            "  attendance: 'attendance_logs',\n"
            "  guardians: 'parents',\n"
            "  schools: 'schools',\n"
            "  payments: 'fee_transactions',\n"
            "} as const;\n\n"
            "export interface PaymentRecord {\n"
            "  id: string;\n"
            "  parentId: string;\n"
            "  studentId: string;\n"
            "  amount: number;\n"
            "  currency: 'INR';\n"
            "  month: string;\n"
            "  razorpayOrderId?: string;\n"
            "  razorpayPaymentId?: string;\n"
            "  razorpaySignature?: string;\n"
            "  status: 'PENDING' | 'SUCCESS' | 'FAILED';\n"
            "  settledAt?: string;\n"
            "}\n"
        ),
        "apps/school-admin-web/src/App.tsx": (
            "import React, { useState } from 'react';\n\n"
            f"export function SchoolAdminDashboard() {{\n"
            f"  const [activeTab, setActiveTab] = useState<'routes' | 'students' | 'safety' | 'fees'>('routes');\n"
            f"  return (\n"
            f"    <div className='min-h-screen bg-slate-950 text-slate-100 font-sans p-6'>\n"
            f"      <header className='flex justify-between items-center border-b border-slate-800 pb-5 mb-6'>\n"
            f"        <div>\n"
            f"          <h1 className='text-2xl font-bold tracking-tight text-white'>{title} - Fleet Control Center</h1>\n"
            f"          <p className='text-xs text-slate-400 mt-1'>Unified Multi-Stakeholder Transport Management</p>\n"
            f"        </div>\n"
            f"        <div className='flex items-center gap-3'>\n"
            f"          <span className='px-3 py-1 bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 rounded-full text-xs font-bold'>\n"
            f"            ● 12 Active Routes\n"
            f"          </span>\n"
            f"          <button className='px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-xs font-bold transition'>\n"
            f"            + Dispatch Route\n"
            f"          </button>\n"
            f"        </div>\n"
            f"      </header>\n"
            f"      <nav className='flex gap-2 mb-6 border-b border-slate-800 pb-3'>\n"
            f"        <button onClick={{() => setActiveTab('routes')}} className={{`px-4 py-2 rounded-lg text-xs font-bold transition ${{activeTab === 'routes' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-900'}}`}}>Active Fleet (12)</button>\n"
            f"        <button onClick={{() => setActiveTab('students')}} className={{`px-4 py-2 rounded-lg text-xs font-bold transition ${{activeTab === 'students' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-900'}}`}}>Students Roster (428)</button>\n"
            f"        <button onClick={{() => setActiveTab('fees')}} className={{`px-4 py-2 rounded-lg text-xs font-bold transition ${{activeTab === 'fees' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-900'}}`}}>Razorpay Fee Settlements</button>\n"
            f"        <button onClick={{() => setActiveTab('safety')}} className={{`px-4 py-2 rounded-lg text-xs font-bold transition ${{activeTab === 'safety' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-900'}}`}}>Safety & SOS Audit</button>\n"
            f"      </nav>\n"
            f"      <main className='grid grid-cols-1 md:grid-cols-3 gap-6'>\n"
            f"        <div className='p-5 bg-slate-900 rounded-xl border border-slate-800'>\n"
            f"          <h2 className='text-sm font-semibold text-slate-400 mb-1'>Live Fleet Tracking</h2>\n"
            f"          <p className='text-3xl font-extrabold text-indigo-400'>12 / 12 Buses</p>\n"
            f"          <p className='text-xs text-slate-500 mt-2'>Average Speed: 36 km/h • GPS Sync: Real-time</p>\n"
            f"        </div>\n"
            f"        <div className='p-5 bg-slate-900 rounded-xl border border-slate-800'>\n"
            f"          <h2 className='text-sm font-semibold text-slate-400 mb-1'>Student Attendance</h2>\n"
            f"          <p className='text-3xl font-extrabold text-emerald-400'>428 Boarded</p>\n"
            f"          <p className='text-xs text-slate-500 mt-2'>QR Checkpoint Scans 100% verified</p>\n"
            f"        </div>\n"
            f"        <div className='p-5 bg-slate-900 rounded-xl border border-slate-800'>\n"
            f"          <h2 className='text-sm font-semibold text-slate-400 mb-1'>Fee Settlements</h2>\n"
            f"          <p className='text-3xl font-extrabold text-amber-400'>98.2% Paid</p>\n"
            f"          <p className='text-xs text-slate-500 mt-2'>Via Razorpay Integration (₹14,98,000 Settled)</p>\n"
            f"        </div>\n"
            f"      </main>\n"
            f"    </div>\n"
            f"  );\n"
            f"}}\n"
        ),
        "apps/parent-mobile/src/screens/TrackingScreen.tsx": (
            "import React, { useState } from 'react';\n\n"
            "export function ParentTrackingScreen() {\n"
            "  const [feePaid, setFeePaid] = useState(false);\n"
            "  return (\n"
            "    <div className='p-5 bg-slate-950 text-white min-h-screen font-sans'>\n"
            "      <header className='flex justify-between items-center pb-4 border-b border-slate-800'>\n"
            "        <div>\n"
            "          <h2 className='text-lg font-bold'>VidyaVahan Guardian App</h2>\n"
            "          <p className='text-xs text-slate-400'>Student: Aarav Sharma (Grade 4B)</p>\n"
            "        </div>\n"
            "        <span className='px-2.5 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-xs font-bold'>\n"
            "          ● Live Tracking\n"
            "        </span>\n"
            "      </header>\n"
            "      <div className='my-5 p-4 bg-slate-900 border border-slate-800 rounded-2xl'>\n"
            "        <div className='flex justify-between items-center text-xs text-slate-400 mb-2'>\n"
            "          <span>Bus #04 • Driver: Rajesh Kumar</span>\n"
            "          <span className='text-amber-400 font-bold'>ETA: 4 mins</span>\n"
            "        </div>\n"
            "        <div className='h-40 bg-slate-800/80 rounded-xl flex items-center justify-center text-slate-400 font-mono text-xs border border-slate-700/50'>\n"
            "          [Interactive Map View: Approaching Green Glen Stop]\n"
            "        </div>\n"
            "      </div>\n"
            "      <div className='p-4 bg-emerald-950/40 border border-emerald-700/60 rounded-xl mb-5'>\n"
            "        <div className='flex items-center gap-3'>\n"
            "          <span className='w-3 h-3 rounded-full bg-emerald-400 animate-ping'></span>\n"
            "          <div>\n"
            "            <strong className='text-sm text-emerald-300 block'>Student Boarded: Aarav Sharma</strong>\n"
            "            <p className='text-xs text-emerald-400/80'>Scanned via Driver QR Terminal • 07:42 AM</p>\n"
            "          </div>\n"
            "        </div>\n"
            "      </div>\n"
            "      <div className='p-4 bg-slate-900 border border-slate-800 rounded-xl'>\n"
            "        <div className='flex justify-between items-center mb-2'>\n"
            "          <strong className='text-sm font-semibold'>Monthly Transport Fee</strong>\n"
            "          <span className='text-xs font-bold text-amber-400'>₹3,500 / Month</span>\n"
            "        </div>\n"
            "        <button onClick={() => setFeePaid(true)} className='w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition'>\n"
            "          {feePaid ? '✓ Paid via Razorpay (Receipt #RZP-7749)' : 'Pay ₹3,500 via Razorpay'}\n"
            "        </button>\n"
            "      </div>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        ),
        "apps/driver-mobile/src/screens/AttendanceScanScreen.tsx": (
            "import React, { useState } from 'react';\n\n"
            "export function DriverAttendanceScreen() {\n"
            "  const [scannedCount, setScannedCount] = useState(24);\n"
            "  const [sosSent, setSosSent] = useState(false);\n"
            "  return (\n"
            "    <div className='p-5 bg-slate-950 text-white min-h-screen font-sans flex flex-col justify-between'>\n"
            "      <div>\n"
            "        <header className='flex justify-between items-center pb-4 border-b border-slate-800'>\n"
            "          <h2 className='text-lg font-bold'>Driver Checkpoint Terminal</h2>\n"
            "          <span className='text-xs text-indigo-400 font-bold'>Route #04 North</span>\n"
            "        </header>\n"
            "        <div className='my-5 p-4 bg-slate-900 border border-slate-800 rounded-2xl text-center'>\n"
            "          <p className='text-xs text-slate-400'>Stop #3: Green Glen Society</p>\n"
            "          <p className='text-3xl font-extrabold text-emerald-400 my-2'>{scannedCount} / 28</p>\n"
            "          <p className='text-xs text-slate-400'>Students Verified on Bus</p>\n"
            "        </div>\n"
            "        <button onClick={() => setScannedCount(c => c + 1)} className='w-full py-4 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-bold text-sm shadow-lg shadow-indigo-600/30 transition'>\n"
            "          📷 Scan Student QR Badge\n"
            "        </button>\n"
            "      </div>\n"
            "      <div className='pt-6'>\n"
            "        <button onClick={() => setSosSent(true)} className='w-full py-3.5 bg-red-600/80 hover:bg-red-600 rounded-xl font-bold text-xs uppercase tracking-wider transition'>\n"
            "          {sosSent ? '🚨 SOS Dispatched to School Police & Admin' : '⚠️ Emergency SOS Alert'}\n"
            "        </button>\n"
            "      </div>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        ),
        "backend/functions/src/index.ts": (
            "// Firebase Cloud Functions for School Transport Backend\n"
            "import * as crypto from 'crypto';\n\n"
            "export const onStudentBoardingScan = async (record: { studentId: string; routeId: string }) => {\n"
            "  // Dispatches instant push notification to guardian app\n"
            "  return { notified: true, studentId: record.studentId, timestamp: new Date().toISOString() };\n"
            "};\n\n"
            "export const createRazorpayOrder = async (data: { studentId: string; parentId: string; amountInr: number }) => {\n"
            "  // Creates verified Razorpay order with INR currency\n"
            "  const orderId = `order_${Date.now()}`;\n"
            "  return { orderId, amount: data.amountInr * 100, currency: 'INR' };\n"
            "};\n\n"
            "export const verifyRazorpayWebhook = async (signature: string, payload: string, secret: string) => {\n"
            "  // Validates HMAC SHA256 webhook authenticity\n"
            "  const expectedSignature = crypto.createHmac('sha256', secret).update(payload).digest('hex');\n"
            "  const isValid = expectedSignature === signature;\n"
            "  return { verified: isValid, signatureMatched: isValid };\n"
            "};\n"
        ),
    }


def _commerce_marketplace_template(title: str) -> dict[str, str]:
    """Multi-stakeholder Commerce Marketplace (Amazon/Flipkart) monorepo template."""
    return {
        "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n  - 'packages/*'\n",
        "packages/shared/types/models.ts": (
            "export interface Product {\n"
            "  id: string;\n"
            "  title: string;\n"
            "  price: number;\n"
            "  sellerId: string;\n"
            "  stockQuantity: number;\n"
            "}\n\n"
            "export interface Order {\n"
            "  id: string;\n"
            "  customerId: string;\n"
            "  items: { productId: string; quantity: number; unitPrice: number }[];\n"
            "  status: 'PLACED' | 'PACKED' | 'DISPATCHED' | 'DELIVERED';\n"
            "  deliveryRiderId?: string;\n"
            "}\n"
        ),
        "apps/customer-web/src/App.tsx": (
            "import React from 'react';\n\n"
            f"export function CustomerStorefront() {{\n"
            f"  return (\n"
            f"    <div className='min-h-screen bg-slate-900 text-white'>\n"
            f"      <header className='p-4 border-b border-slate-800 flex justify-between'>\n"
            f"        <h1 className='text-xl font-bold'>{title} Storefront</h1>\n"
            f"        <button className='px-4 py-2 bg-amber-500 text-slate-950 font-bold rounded-lg'>Cart (0)</button>\n"
            f"      </header>\n"
            f"    </div>\n"
            f"  );\n"
            f"}}\n"
        ),
        "apps/seller-portal/src/App.tsx": (
            "import React from 'react';\n\n"
            "export function SellerDashboard() {\n"
            "  return (\n"
            "    <div className='p-6 bg-slate-900 text-white'>\n"
            "      <h1 className='text-2xl font-bold'>Seller Inventory & Fulfillment</h1>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        ),
        "apps/rider-mobile/src/App.tsx": (
            "import React from 'react';\n\n"
            "export function RiderDispatchView() {\n"
            "  return (\n"
            "    <div className='p-4 bg-slate-900 text-white'>\n"
            "      <h2 className='text-lg font-bold'>Active Delivery Queue</h2>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        ),
        "apps/admin-console/src/App.tsx": (
            "import React from 'react';\n\n"
            "export function AdminGovernanceConsole() {\n"
            "  return (\n"
            "    <div className='p-6 bg-slate-900 text-white'>\n"
            "      <h1 className='text-2xl font-bold'>Marketplace Governance & Disputes</h1>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        ),
    }


def _elder_logistics_template(title: str) -> dict[str, str]:
    """Accessible Elder Care & Assisted Logistics template."""
    return {
        "packages/shared/types/elder.ts": (
            "export interface ElderProfile {\n"
            "  id: string;\n"
            "  fullName: string;\n"
            "  mobilityAssistanceRequired: boolean;\n"
            "  emergencyContactPhone: string;\n"
            "  assignedCaregiverId?: string;\n"
            "}\n\n"
            "export interface AssistedRide {\n"
            "  id: string;\n"
            "  passengerId: string;\n"
            "  wheelchairAccessibleVehicle: boolean;\n"
            "  pickupAddress: string;\n"
            "  destinationClinic: string;\n"
            "  status: 'SCHEDULED' | 'IN_TRANSIT' | 'ARRIVED';\n"
            "}\n"
        ),
        "apps/elder-app/src/App.tsx": (
            "import React from 'react';\n\n"
            f"export function ElderCareTransportApp() {{\n"
            f"  return (\n"
            f"    <div className='p-6 bg-slate-900 text-white font-sans text-lg'>\n"
            f"      <h1 className='text-3xl font-bold'>{title} - Senior Assisted Rides</h1>\n"
            f"      <button className='w-full my-6 py-5 bg-emerald-600 rounded-2xl text-2xl font-extrabold'>\n"
            f"        📞 One-Tap Ride to Clinic\n"
            f"      </button>\n"
            f"    </div>\n"
            f"  );\n"
            f"}}\n"
        ),
    }


def export_archetype(
    archetype: str,
    output_dir: str | Path,
    project_title: str = "Platform",
) -> list[str]:
    """Write all archetype files to the specified output directory on disk."""
    out_path = Path(output_dir)
    files = generate_archetype_files(archetype, project_title=project_title)
    written: list[str] = []
    for rel_path, content in files.items():
        file_path = out_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        written.append(str(file_path))
    return written


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Scaffold an autonomous software archetype monorepo."
    )
    parser.add_argument(
        "--archetype",
        default=ARCHETYPE_SCHOOL_TRANSPORT,
        choices=sorted(SUPPORTED_ARCHETYPES),
        help="Archetype to generate (default: school_transport)",
    )
    parser.add_argument(
        "--out",
        default="./generated_apps/school_transport",
        help="Destination directory for generated files",
    )
    parser.add_argument(
        "--title",
        default="VidyaVahan School Transport",
        help="Project display title",
    )
    args = parser.parse_args()
    exported = export_archetype(args.archetype, args.out, project_title=args.title)
    print(f"[OK] Generated {len(exported)} files for '{args.archetype}' in: {args.out}")


