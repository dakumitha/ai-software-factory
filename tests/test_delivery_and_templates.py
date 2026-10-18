"""Tests for multi-stakeholder templates, release gates, and deployment controller."""
import tempfile
import unittest
from pathlib import Path

from software_factory.core import Store
from software_factory.delivery import DeliveryError, ReleaseController
from software_factory.evidence_store import EvidenceStore
from software_factory.templates import (
    ARCHETYPE_COMMERCE_MARKETPLACE,
    ARCHETYPE_ELDER_LOGISTICS,
    ARCHETYPE_SCHOOL_TRANSPORT,
    generate_archetype_files,
)


class TemplatesAndDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.db_path = self.base_dir / "factory.sqlite3"
        self.store = Store(self.db_path)
        self.evidence_store = EvidenceStore(self.db_path)
        self.release_controller = ReleaseController(self.store, self.evidence_store)
        self.project = self.store.create_project("School App", "Monorepo for transport")

    def tearDown(self):
        self.tmp.cleanup()

    def test_school_transport_template_generates_all_stakeholder_apps(self):
        files = generate_archetype_files(ARCHETYPE_SCHOOL_TRANSPORT, project_title="Delhi Public School")
        self.assertIn("pnpm-workspace.yaml", files)
        self.assertIn("turbo.json", files)
        self.assertIn("packages/shared/types/transport.ts", files)
        self.assertIn("packages/shared/firebase.ts", files)
        self.assertIn("apps/school-admin-web/src/App.tsx", files)
        self.assertIn("apps/parent-mobile/src/screens/TrackingScreen.tsx", files)
        self.assertIn("apps/driver-mobile/src/screens/AttendanceScanScreen.tsx", files)
        self.assertIn("backend/functions/src/index.ts", files)

        # Content assertions
        self.assertIn("Delhi Public School", files["apps/school-admin-web/src/App.tsx"])
        self.assertIn("Student Boarded", files["apps/parent-mobile/src/screens/TrackingScreen.tsx"])
        self.assertIn("razorpayOrderId", files["packages/shared/firebase.ts"])

    def test_commerce_and_elder_templates(self):
        comm_files = generate_archetype_files(ARCHETYPE_COMMERCE_MARKETPLACE, project_title="MegaShop")
        self.assertIn("apps/customer-web/src/App.tsx", comm_files)
        self.assertIn("apps/seller-portal/src/App.tsx", comm_files)
        self.assertIn("apps/rider-mobile/src/App.tsx", comm_files)
        self.assertIn("apps/admin-console/src/App.tsx", comm_files)

        elder_files = generate_archetype_files(ARCHETYPE_ELDER_LOGISTICS, project_title="SilverCare")
        self.assertIn("apps/elder-app/src/App.tsx", elder_files)

    def test_release_controller_blocks_unverified_job(self):
        job = self.store.create_job(
            self.project["id"],
            tasks=[{"id": "t1", "title": "Task 1", "type": "artifact_integrity"}],
        )
        for s in ("NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY", "AWAITING_APPROVAL", "QUEUED", "RUNNING"):
            self.store.transition(job["id"], s)

        # Should be blocked because tasks are unfinished and state is RUNNING
        readiness = self.release_controller.evaluate_release_readiness(job["id"])
        self.assertFalse(readiness["can_release"])
        self.assertGreater(len(readiness["blocking_reasons"]), 0)

        with self.assertRaises(DeliveryError):
            self.release_controller.promote_to_release_ready(job["id"])

    def test_release_controller_promotes_releases_and_rolls_back(self):
        job = self.store.create_job(
            self.project["id"],
            tasks=[{"id": "t1", "title": "Task 1", "type": "artifact_integrity"}],
        )
        for s in ("NEEDS_CLARIFICATION", "SPEC_READY", "PLAN_READY", "AWAITING_APPROVAL", "QUEUED", "RUNNING", "VERIFYING", "REVIEW_REQUIRED"):
            self.store.transition(job["id"], s)

        # Complete task in checkpoint
        self.store.save_checkpoint(job["id"], {"completed_task_ids": ["t1"]})

        # Record passing evidence
        self.evidence_store.record_test_log(
            job_id=job["id"],
            task_id="t1",
            attempt_id="att-1",
            command="npm test",
            exit_code=0,
            stdout="OK",
            stderr="",
        )

        readiness = self.release_controller.evaluate_release_readiness(job["id"])
        self.assertTrue(readiness["can_release"])

        promoted = self.release_controller.promote_to_release_ready(job["id"], actor="test-lead")
        self.assertEqual(promoted["state"], "RELEASE_READY")

        released = self.release_controller.execute_release(job["id"], actor="release-lead", notes="Production release")
        self.assertEqual(released["state"], "RELEASED")
        self.assertIn("release_receipt", released["checkpoint"])

        # Rollback
        rolled_back = self.release_controller.rollback_release(job["id"], actor="ops", reason="Hotfix rollback")
        self.assertEqual(rolled_back["state"], "QUEUED")


if __name__ == "__main__":
    unittest.main()

