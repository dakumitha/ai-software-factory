"""Regression tests for the isolated, deterministic demo workflow."""
import unittest

from software_factory.demo import run_demo


class DemoTests(unittest.TestCase):
    def test_demo_completes_orchestration_without_claiming_release(self):
        report = run_demo()

        self.assertEqual(report["demo_mode"], "deterministic_dry_run")
        self.assertEqual(report["external_network_calls"], 0)
        self.assertEqual(report["ai_provider_calls"], 0)
        self.assertEqual(report["shell_commands_executed"], 0)
        self.assertEqual(report["specification_status"], "APPROVED")
        self.assertEqual(report["planned_task_count"], report["successful_demo_task_count"])
        self.assertEqual(report["final_job_state"], "REVIEW_REQUIRED")
        self.assertFalse(report["release_performed"])
        self.assertTrue(report["limitations"])

    def test_demo_is_repeatable_and_uses_disposable_records(self):
        first = run_demo()
        second = run_demo()

        self.assertEqual(first["planned_task_count"], second["planned_task_count"])
        self.assertEqual(first["successful_demo_task_count"], second["successful_demo_task_count"])
        self.assertEqual(first["final_job_state"], second["final_job_state"])


if __name__ == "__main__":
    unittest.main()
