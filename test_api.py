"""
Comprehensive Test Suite for JP-001 Duplicate Application Manager API & Services.
Verifies all endpoints, scanning engine, content fingerprinting, quarantine, restore, and audit trail.
"""

import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from api.main import app
from core.config import settings
from core.database import Base, engine, init_db, SessionLocal
from core.models import Application, CategorizationRule, DuplicateGroup, RemovalAction, ScanJob
from services.scan_service import compute_application_fingerprint, compute_file_sha256, ScanWorker


class TestJP001APIAndServices(unittest.TestCase):
    """Integration and unit tests for JP-001."""

    @classmethod
    def setUpClass(cls):
        # Initialize test DB
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("version", data)

    def test_dashboard_stats(self):
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_applications", data)
        self.assertIn("duplicate_groups_count", data)
        self.assertIn("reclaimable_bytes", data)

    def test_deterministic_fingerprint_generation(self):
        files_a = [
            ("file1.exe", 1024, "aabbcc112233"),
            ("config.json", 256, "ddeeff445566"),
        ]
        # Same files in different order
        files_b = [
            ("config.json", 256, "ddeeff445566"),
            ("file1.exe", 1024, "aabbcc112233"),
        ]

        fp_a = compute_application_fingerprint(files_a)
        fp_b = compute_application_fingerprint(files_b)
        self.assertEqual(fp_a, fp_b, "Fingerprint must be deterministic regardless of input ordering")

    def test_rule_crud_endpoints(self):
        # 1. Create Rule
        payload = {
            "name": "Custom Test Rule",
            "priority": 15,
            "category": "TestCategory",
            "conditions": {
                "extensions": [".testext"],
                "keywords": ["customtest"],
                "path_patterns": ["*/testdir/*"]
            },
            "enabled": True
        }
        res_create = self.client.post("/api/rules", json=payload)
        self.assertEqual(res_create.status_code, 201)
        rule_data = res_create.json()
        rule_id = rule_data["id"]
        self.assertEqual(rule_data["name"], "Custom Test Rule")

        # 2. List Rules
        res_list = self.client.get("/api/rules")
        self.assertEqual(res_list.status_code, 200)
        rules = res_list.json()
        self.assertTrue(any(r["id"] == rule_id for r in rules))

        # 3. Update Rule
        res_update = self.client.put(f"/api/rules/{rule_id}", json={"priority": 5, "name": "Updated Test Rule"})
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json()["priority"], 5)
        self.assertEqual(res_update.json()["name"], "Updated Test Rule")

        # 4. Delete Rule
        res_del = self.client.delete(f"/api/rules/{rule_id}")
        self.assertEqual(res_del.status_code, 204)

    def test_scan_and_duplicate_detection_lifecycle(self):
        # Create test folders with duplicates
        folder1 = self.test_dir / "app_instance_1"
        folder2 = self.test_dir / "app_instance_2"
        folder1.mkdir(parents=True)
        folder2.mkdir(parents=True)

        payload_content = b"TEST_BINARY_IDENTICAL_DATA" * 50
        (folder1 / "app.exe").write_bytes(payload_content)
        (folder2 / "app_renamed.exe").write_bytes(payload_content)

        # Unique file
        (self.test_dir / "unique.py").write_bytes(b"print('unique script')")

        # Launch scan synchronously via ScanWorker
        scan_job = ScanJob(status="queued", roots=[str(self.test_dir)])
        self.db.add(scan_job)
        self.db.commit()
        self.db.refresh(scan_job)

        worker = ScanWorker(scan_job.id)
        worker.run()

        # Check completed scan job in DB
        self.db.refresh(scan_job)
        self.assertEqual(scan_job.status, "completed")
        self.assertEqual(scan_job.apps_found, 3)
        self.assertEqual(scan_job.duplicates_found, 2)

        # Verify duplicate group endpoint
        res_dups = self.client.get("/api/duplicates")
        self.assertEqual(res_dups.status_code, 200)
        dups = res_dups.json()
        self.assertGreaterEqual(len(dups), 1)

        # Verify duplicate detail endpoint
        dup_id = dups[0]["id"]
        res_dup_detail = self.client.get(f"/api/duplicates/{dup_id}")
        self.assertEqual(res_dup_detail.status_code, 200)
        detail = res_dup_detail.json()
        self.assertEqual(len(detail["members"]), 2)

    def test_quarantine_preview_and_execution_and_restore(self):
        # Create test file to quarantine
        test_file = self.test_dir / "redundant_app.exe"
        test_file.write_bytes(b"BINARY_FOR_QUARANTINE" * 30)

        # Register Application in DB
        app_record = Application(
            name="redundant_app.exe",
            path=str(test_file.resolve()),
            category="Utilities & Tools",
            content_fingerprint="dummy_fp_12345",
            total_size=len(test_file.read_bytes()),
            file_count=1,
        )
        self.db.add(app_record)
        self.db.commit()
        self.db.refresh(app_record)

        # 1. Test Preview
        res_preview = self.client.post("/api/removals/preview", json={"application_id": app_record.id})
        self.assertEqual(res_preview.status_code, 200)
        preview_data = res_preview.json()
        self.assertTrue(preview_data["is_safe"])
        self.assertEqual(preview_data["name"], "redundant_app.exe")

        # 2. Test Quarantine without Confirmation (should fail with 400)
        res_unconfirmed = self.client.post("/api/removals", json={"application_id": app_record.id, "confirm": False})
        self.assertEqual(res_unconfirmed.status_code, 400)
        self.assertTrue(test_file.exists(), "File should still exist on unconfirmed quarantine")

        # 3. Test Quarantine with Confirmation
        res_quarantine = self.client.post("/api/removals", json={"application_id": app_record.id, "confirm": True})
        self.assertEqual(res_quarantine.status_code, 201)
        action_data = res_quarantine.json()
        action_id = action_data["id"]
        self.assertEqual(action_data["status"], "completed")
        self.assertFalse(test_file.exists(), "Original file should have been moved into quarantine")

        # Verify quarantine file exists in quarantine directory
        quarantine_file = Path(action_data["quarantine_path"])
        self.assertTrue(quarantine_file.exists(), "File must exist in quarantine location")

        # 4. Test Restore
        res_restore = self.client.post(f"/api/removals/{action_id}/restore")
        self.assertEqual(res_restore.status_code, 200)
        self.assertTrue(test_file.exists(), "File must be restored back to original location")
        self.assertFalse(quarantine_file.exists(), "File should be moved out of quarantine")

    def test_audit_log_endpoint(self):
        from services.audit_service import record_audit
        record_audit(self.db, action="TEST_AUDIT_ACTION", entity_type="test_entity", details={"key": "val"})

        # Fetch audit logs
        res_audit = self.client.get("/api/audit")
        self.assertEqual(res_audit.status_code, 200)
        logs = res_audit.json()
        self.assertIsInstance(logs, list)
        self.assertGreater(len(logs), 0)
        self.assertTrue(any(l["action"] == "TEST_AUDIT_ACTION" for l in logs))

        # Test filtering by action
        res_filtered = self.client.get("/api/audit?action=TEST_AUDIT_ACTION")
        self.assertEqual(res_filtered.status_code, 200)
        filtered_logs = res_filtered.json()
        self.assertTrue(all(l["action"] == "TEST_AUDIT_ACTION" for l in filtered_logs))


if __name__ == "__main__":
    unittest.main()
