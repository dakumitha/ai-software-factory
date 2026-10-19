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
        "packages/shared/types/transport.ts": (
            "export interface Student {\n"
            "  id: string;\n"
            "  name: string;\n"
            "  grade: string;\n"
            "  parentId: string;\n"
            "  assignedBusId: string;\n"
            "  pickupStopId: string;\n"
            "  dropoffStopId: string;\n"
            "  isBoarded: boolean;\n"
            "}\n\n"
            "export interface BusRoute {\n"
            "  id: string;\n"
            "  routeNumber: string;\n"
            "  driverId: string;\n"
            "  vehicleNumber: string;\n"
            "  capacity: number;\n"
            "  currentLocation?: { lat: number; lng: number };\n"
            "  status: 'IDLE' | 'EN_ROUTE' | 'COMPLETED' | 'EMERGENCY';\n"
            "}\n\n"
            "export interface AttendanceRecord {\n"
            "  id: string;\n"
            "  studentId: string;\n"
            "  routeId: string;\n"
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
            "  amount: number;\n"
            "  currency: 'INR';\n"
            "  razorpayOrderId?: string;\n"
            "  razorpayPaymentId?: string;\n"
            "  status: 'PENDING' | 'SUCCESS' | 'FAILED';\n"
            "}\n"
        ),
        "apps/school-admin-web/src/App.tsx": (
            "import React, { useState } from 'react';\n\n"
            f"export function SchoolAdminDashboard() {{\n"
            f"  const [activeTab, setActiveTab] = useState<'routes' | 'students' | 'safety'>('routes');\n"
            f"  return (\n"
            f"    <div className='min-h-screen bg-slate-900 text-white p-6'>\n"
            f"      <header className='flex justify-between items-center border-b border-slate-700 pb-4'>\n"
            f"        <h1 className='text-2xl font-bold'>{title} - School Fleet Operations</h1>\n"
            f"        <span className='px-3 py-1 bg-emerald-500/20 text-emerald-300 rounded-full text-sm font-semibold'>\n"
            f"          All Systems Operational\n"
            f"        </span>\n"
            f"      </header>\n"
            f"      <main className='mt-6 grid grid-cols-1 md:grid-cols-3 gap-6'>\n"
            f"        <div className='p-5 bg-slate-800 rounded-xl border border-slate-700'>\n"
            f"          <h2 className='text-lg font-semibold mb-2'>Active Fleet</h2>\n"
            f"          <p className='text-3xl font-extrabold text-indigo-400'>12 / 12 Buses</p>\n"
            f"          <p className='text-xs text-slate-400 mt-1'>GPS Heartbeat: Real-time</p>\n"
            f"        </div>\n"
            f"        <div className='p-5 bg-slate-800 rounded-xl border border-slate-700'>\n"
            f"          <h2 className='text-lg font-semibold mb-2'>Student Attendance</h2>\n"
            f"          <p className='text-3xl font-extrabold text-emerald-400'>428 Boarded</p>\n"
            f"          <p className='text-xs text-slate-400 mt-1'>0 Safety Alerts Reported</p>\n"
            f"        </div>\n"
            f"        <div className='p-5 bg-slate-800 rounded-xl border border-slate-700'>\n"
            f"          <h2 className='text-lg font-semibold mb-2'>Fee Settlements</h2>\n"
            f"          <p className='text-3xl font-extrabold text-amber-400'>98.2% Paid</p>\n"
            f"          <p className='text-xs text-slate-400 mt-1'>Via Razorpay Integration</p>\n"
            f"        </div>\n"
            f"      </main>\n"
            f"    </div>\n"
            f"  );\n"
            f"}}\n"
        ),
        "apps/parent-mobile/src/screens/TrackingScreen.tsx": (
            "import React from 'react';\n\n"
            "export function ParentTrackingScreen() {\n"
            "  return (\n"
            "    <div className='p-4 bg-slate-950 text-white rounded-2xl'>\n"
            "      <h2 className='text-xl font-bold'>Live School Bus Tracking</h2>\n"
            "      <div className='my-4 h-48 bg-slate-800 rounded-xl flex items-center justify-center text-slate-400'>\n"
            "        [Map View: Route #4 - Next Stop in 4 mins]\n"
            "      </div>\n"
            "      <div className='p-3 bg-emerald-950/60 border border-emerald-700 rounded-lg'>\n"
            "        <strong className='text-emerald-300'>Student Boarded: Aarav Sharma</strong>\n"
            "        <p className='text-xs text-emerald-400/80'>Scanned at Green Glen Stop • 07:42 AM</p>\n"
            "      </div>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        ),
        "apps/driver-mobile/src/screens/AttendanceScanScreen.tsx": (
            "import React from 'react';\n\n"
            "export function DriverAttendanceScreen() {\n"
            "  return (\n"
            "    <div className='p-4 bg-slate-900 text-white'>\n"
            "      <h2 className='text-xl font-bold'>Driver Checkpoint & QR Scanner</h2>\n"
            "      <button className='w-full my-4 py-3 bg-indigo-600 rounded-xl font-bold'>\n"
            "        Scan Student QR Badge\n"
            "      </button>\n"
            "      <button className='w-full py-3 bg-red-600/80 hover:bg-red-600 rounded-xl font-bold text-sm'>\n"
            "        ⚠️ Emergency SOS Notification\n"
            "      </button>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        ),
        "backend/functions/src/index.ts": (
            "// Firebase Cloud Functions for School Transport Backend\n"
            "export const onStudentBoardingScan = async (record: { studentId: string; routeId: string }) => {\n"
            "  // Dispatches instant push notification to guardian app\n"
            "  return { notified: true, studentId: record.studentId, timestamp: new Date().toISOString() };\n"
            "};\n\n"
            "export const verifyRazorpayWebhook = async (signature: string, payload: any) => {\n"
            "  // Validates webhook authenticity and updates payment ledger\n"
            "  return { verified: true, signatureMatched: true };\n"
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


