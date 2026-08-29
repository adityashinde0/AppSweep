"""
Comprehensive Unit Test Suite for Intelligent Application Management Tool.

Verifies:
- Size pre-filtering optimization (skipping unique-sized files)
- SHA-256 memory-buffered 64 KB chunked streaming accuracy and custom buffer sizes
- Rule-based categorization, keyword/extension matching, and fallback handling
- Windows path normalization and cross-platform path pattern evaluation
- Multi-directory duplicate detection and category summary table generation
- Console progress bar updates and non-TTY fallback
- Deletion safety (dry-run simulation vs real deletion)
- Robust error handling for invalid paths, unreadable files, system-protected directories, and corrupted JSON
"""

import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app import (
    ApplicationManager,
    DEFAULT_CHUNK_SIZE,
    display_category_breakdown_table,
    display_duplicate_summary,
    FileRecord,
    format_bytes,
    interactive_duplicate_resolution,
    normalize_path,
    ProgressBar,
    Rule,
    RuleEngine,
)


class TestFormattingAndDataModels(unittest.TestCase):
    """Test format helpers, path normalization, and core data models."""

    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(512), "512 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1536), "1.50 KB")
        self.assertEqual(format_bytes(1024 * 1024), "1.00 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024 * 2), "2.00 GB")
        self.assertEqual(format_bytes(-50), "0 B")

    def test_normalize_path(self):
        cur_dir = normalize_path(".")
        self.assertTrue(cur_dir.is_absolute())
        # Test backslash path normalization
        win_style = normalize_path(r".\app.py")
        self.assertTrue(win_style.is_absolute())
        self.assertTrue(str(win_style).endswith("app.py"))

    def test_file_record_properties(self):
        record = FileRecord(
            path=Path("/tmp/test_binary.exe"),
            size=2048,
            category="Utilities & Tools",
            sha256_hash="abcdef123456",
            modified_time=1000.0,
        )
        self.assertEqual(record.formatted_size, "2.00 KB")
        self.assertEqual(record.category, "Utilities & Tools")


class TestProgressBar(unittest.TestCase):
    """Test visual console progress bar logic and non-TTY fallbacks."""

    def test_progress_bar_updates(self):
        mock_logger = MagicMock()
        bar = ProgressBar(total=10, prefix="Testing", logger=mock_logger)
        bar.update(1, "file1.exe")
        bar.update(5, "file5.exe")
        bar.update(10, "file10.exe")
        bar.finish("All done")
        self.assertEqual(bar.current, 10)

    def test_progress_bar_zero_total_safe(self):
        bar = ProgressBar(total=0)
        self.assertEqual(bar.total, 1)
        bar.update(1)
        bar.finish()


class TestSHA256Hashing(unittest.TestCase):
    """Test chunked cryptographic hashing functionality and memory buffer management."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = ApplicationManager(rules_path=None, chunk_size=DEFAULT_CHUNK_SIZE)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_hashing_accuracy_matches_hashlib(self):
        test_payload = b"ProductionGradeAppBinaryContent" * 1000
        test_file = Path(self.test_dir) / "binary_payload.bin"
        test_file.write_bytes(test_payload)

        expected_hash = hashlib.sha256(test_payload).hexdigest()
        computed_hash = self.manager.compute_sha256(test_file)

        self.assertEqual(computed_hash, expected_hash)

    def test_chunked_streaming_small_buffer(self):
        # 100 KB payload with a tiny 32-byte chunk size to exercise multi-chunk iterations
        test_payload = os.urandom(100 * 1024)
        test_file = Path(self.test_dir) / "large_payload.bin"
        test_file.write_bytes(test_payload)

        expected_hash = hashlib.sha256(test_payload).hexdigest()
        computed_hash = self.manager.compute_sha256(test_file, chunk_size=32)

        self.assertEqual(computed_hash, expected_hash)

    def test_empty_file_hashing(self):
        empty_file = Path(self.test_dir) / "empty.dat"
        empty_file.write_bytes(b"")

        expected_hash = hashlib.sha256(b"").hexdigest()
        computed_hash = self.manager.compute_sha256(empty_file)

        self.assertEqual(computed_hash, expected_hash)

    def test_non_existent_file_returns_none(self):
        non_existent = Path(self.test_dir) / "does_not_exist.bin"
        self.assertIsNone(self.manager.compute_sha256(non_existent))

    def test_permission_error_handling(self):
        test_file = Path(self.test_dir) / "locked.bin"
        test_file.write_bytes(b"some content")

        with patch("builtins.open", side_effect=PermissionError("Access is denied")):
            hash_result = self.manager.compute_sha256(test_file)
            self.assertIsNone(hash_result)


class TestRuleEngineAndCategorization(unittest.TestCase):
    """Test dynamic JSON rule loading, matching logic, and fallback behavior."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.logger = logging.getLogger("TestLogger")
        self.logger.setLevel(logging.CRITICAL)  # Suppress logs in test output

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_categorization_by_extension(self):
        engine = RuleEngine(rules_path=None, logger=self.logger)
        self.assertEqual(engine.categorize(Path("main.py")), "Development")
        self.assertEqual(engine.categorize(Path("video.mp4")), "Media & Graphics")
        self.assertEqual(engine.categorize(Path("document.pdf")), "Documents & Productivity")
        self.assertEqual(engine.categorize(Path("game_archive.pak")), "Games & Entertainment")
        self.assertEqual(engine.categorize(Path("setup_installer.exe")), "Utilities & Tools")

    def test_categorization_by_keyword(self):
        engine = RuleEngine(rules_path=None, logger=self.logger)
        self.assertEqual(engine.categorize(Path("python_runtime.dat")), "Development")
        self.assertEqual(engine.categorize(Path("ffmpeg_encoder.unknown")), "Media & Graphics")
        self.assertEqual(engine.categorize(Path("cleaner_tool.bin")), "Utilities & Tools")
        self.assertEqual(engine.categorize(Path("financial_report_2026.xyz")), "Documents & Productivity")
        self.assertEqual(engine.categorize(Path("retro_arcade_engine.data")), "Games & Entertainment")

    def test_categorization_by_path_pattern(self):
        engine = RuleEngine(rules_path=None, logger=self.logger)
        path = Path(self.test_dir) / "source" / "nested" / "app_bundle.xyz"
        self.assertEqual(engine.categorize(path), "Development")

    def test_fallback_to_uncategorized(self):
        engine = RuleEngine(rules_path=None, logger=self.logger)
        unknown_file = Path("mystery_object_98765.xyz123")
        self.assertEqual(engine.categorize(unknown_file), "Uncategorized")

    def test_load_custom_rules_from_json(self):
        custom_rules = {
            "rules": [
                {
                    "category": "Cloud & DevOps",
                    "description": "Kubernetes, Terraform, and Docker artifacts",
                    "extensions": [".tf", ".k8s", ".dockerfile"],
                    "keywords": ["helm", "terraform", "docker", "k8s"],
                    "path_patterns": ["*/deploy/*", "*/k8s/*"]
                },
                {
                    "category": "Machine Learning",
                    "description": "Model weights and datasets",
                    "extensions": [".onnx", ".pt", ".pth", ".safetensors"],
                    "keywords": ["model", "weights", "dataset", "transformer"],
                    "path_patterns": ["*/models/*", "*/checkpoints/*"]
                }
            ]
        }
        rules_file = Path(self.test_dir) / "custom_rules.json"
        rules_file.write_text(json.dumps(custom_rules), encoding="utf-8")

        engine = RuleEngine(rules_path=rules_file, logger=self.logger)
        self.assertEqual(len(engine.rules), 2)
        self.assertEqual(engine.categorize(Path("infra.tf")), "Cloud & DevOps")
        self.assertEqual(engine.categorize(Path("bert_weights.safetensors")), "Machine Learning")
        self.assertEqual(engine.categorize(Path("random.txt")), "Uncategorized")

    def test_corrupt_json_fallback(self):
        corrupt_file = Path(self.test_dir) / "bad_rules.json"
        corrupt_file.write_text("{ this is invalid json syntax ::: ", encoding="utf-8")

        engine = RuleEngine(rules_path=corrupt_file, logger=self.logger)
        self.assertGreater(len(engine.rules), 0)
        self.assertEqual(engine.categorize(Path("script.py")), "Development")

    def test_missing_rules_file_fallback(self):
        missing_file = Path(self.test_dir) / "non_existent_rules.json"
        engine = RuleEngine(rules_path=missing_file, logger=self.logger)
        self.assertGreater(len(engine.rules), 0)
        self.assertEqual(engine.categorize(Path("audio.mp3")), "Media & Graphics")


class TestSizePreFilteringAndDuplicateDetection(unittest.TestCase):
    """Test performance-critical size pre-filtering and exact byte duplicate grouping."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = ApplicationManager(rules_path=None, chunk_size=DEFAULT_CHUNK_SIZE)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_size_pre_filter_skips_unique_files(self):
        """
        Verify that files with unique sizes are filtered out prior to SHA-256 hashing.
        """
        base = Path(self.test_dir)

        # File A: 100 bytes (unique size)
        (base / "unique_100.bin").write_bytes(b"A" * 100)
        # File B: 200 bytes (unique size)
        (base / "unique_200.bin").write_bytes(b"B" * 200)
        # File C: 300 bytes (unique size)
        (base / "unique_300.bin").write_bytes(b"C" * 300)

        with patch.object(self.manager, "compute_sha256", wraps=self.manager.compute_sha256) as mock_hash:
            duplicates, all_records = self.manager.find_duplicates(base, show_progress=False)
            self.assertEqual(duplicates, {})
            self.assertEqual(len(all_records), 3)
            # Mock hash should never have been called because all file sizes are unique!
            mock_hash.assert_not_called()

    def test_identical_size_different_content_collision(self):
        """
        Files with identical byte size but different content should be hashed,
        but NOT grouped as duplicates.
        """
        base = Path(self.test_dir)

        # File 1: 50 bytes of 'X'
        (base / "file_x.bin").write_bytes(b"X" * 50)
        # File 2: 50 bytes of 'Y'
        (base / "file_y.bin").write_bytes(b"Y" * 50)

        duplicates, all_records = self.manager.find_duplicates(base, show_progress=False)
        self.assertEqual(duplicates, {})
        self.assertEqual(len(all_records), 2)

    def test_find_exact_duplicates_across_subdirectories(self):
        """
        Files with identical content in different folders and different filenames
        must be correctly grouped under the same SHA-256 hash.
        """
        base = Path(self.test_dir)
        sub1 = base / "folder_alpha"
        sub2 = base / "folder_beta" / "nested"
        sub1.mkdir(parents=True, exist_ok=True)
        sub2.mkdir(parents=True, exist_ok=True)

        payload_app1 = b"\x7fELF\x02\x01\x01\x00" + (b"AppPayload1" * 500)
        payload_app2 = b"\x4d\x5a\x90\x00" + (b"AppPayload2" * 800)

        # Duplicate Group 1: 2 instances
        file1_a = sub1 / "app1.bin"
        file1_b = sub2 / "renamed_app1.exe"
        file1_a.write_bytes(payload_app1)
        file1_b.write_bytes(payload_app1)

        # Duplicate Group 2: 3 instances
        file2_a = base / "service.exe"
        file2_b = sub1 / "service_backup.exe"
        file2_c = sub2 / "service_copy.dll"
        file2_a.write_bytes(payload_app2)
        file2_b.write_bytes(payload_app2)
        file2_c.write_bytes(payload_app2)

        # Unique file
        (base / "unique_script.py").write_bytes(b"print('hello world')")

        duplicates, all_records = self.manager.find_duplicates(base, show_progress=False)

        hash1 = hashlib.sha256(payload_app1).hexdigest()
        hash2 = hashlib.sha256(payload_app2).hexdigest()

        self.assertEqual(len(duplicates), 2)
        self.assertEqual(len(all_records), 6)
        self.assertIn(hash1, duplicates)
        self.assertIn(hash2, duplicates)

        # Group 1 should contain 2 records
        self.assertEqual(len(duplicates[hash1]), 2)
        paths_group1 = {r.path.resolve() for r in duplicates[hash1]}
        self.assertIn(file1_a.resolve(), paths_group1)
        self.assertIn(file1_b.resolve(), paths_group1)

        # Group 2 should contain 3 records
        self.assertEqual(len(duplicates[hash2]), 3)
        paths_group2 = {r.path.resolve() for r in duplicates[hash2]}
        self.assertIn(file2_a.resolve(), paths_group2)
        self.assertIn(file2_b.resolve(), paths_group2)
        self.assertIn(file2_c.resolve(), paths_group2)


class TestDeletionSafetyAndOperations(unittest.TestCase):
    """Test safe file deletion mechanics and dry-run execution."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = ApplicationManager(rules_path=None)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dry_run_simulation_preserves_file(self):
        test_file = Path(self.test_dir) / "important_app.exe"
        test_file.write_bytes(b"binary data")

        success = self.manager.delete_file(test_file, dry_run=True)
        self.assertTrue(success)
        self.assertTrue(test_file.exists(), "Dry-run must not delete the physical file")

    def test_actual_deletion_removes_file(self):
        test_file = Path(self.test_dir) / "redundant_copy.exe"
        test_file.write_bytes(b"binary data")

        success = self.manager.delete_file(test_file, dry_run=False)
        self.assertTrue(success)
        self.assertFalse(test_file.exists(), "File should be removed from disk")

    def test_delete_non_existent_file(self):
        ghost_file = Path(self.test_dir) / "ghost.exe"
        success = self.manager.delete_file(ghost_file, dry_run=False)
        self.assertFalse(success)

    def test_batch_deletion(self):
        f1 = Path(self.test_dir) / "del1.bin"
        f2 = Path(self.test_dir) / "del2.bin"
        f1.write_bytes(b"data1")
        f2.write_bytes(b"data2")

        results = self.manager.batch_delete_files([f1, f2], dry_run=False)
        self.assertEqual(results[f1.resolve()], True)
        self.assertEqual(results[f2.resolve()], True)
        self.assertFalse(f1.exists())
        self.assertFalse(f2.exists())


class TestDirectoryScanningAndErrorHandling(unittest.TestCase):
    """Test directory traversal, path validation, and permission error boundaries."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = ApplicationManager(rules_path=None)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_non_existent_directory_raises_filenotfound(self):
        non_existent = Path(self.test_dir) / "invalid_sub_dir_12345"
        with self.assertRaises(FileNotFoundError):
            self.manager.scan_directory(non_existent)

    def test_file_passed_as_directory_raises_notadirectory(self):
        regular_file = Path(self.test_dir) / "some_file.txt"
        regular_file.write_text("hello", encoding="utf-8")
        with self.assertRaises(NotADirectoryError):
            self.manager.scan_directory(regular_file)

    def test_empty_directory_scan(self):
        files = self.manager.scan_directory(self.test_dir, show_progress=False)
        self.assertEqual(files, [])
        duplicates, all_records = self.manager.find_duplicates(self.test_dir, show_progress=False)
        self.assertEqual(duplicates, {})
        self.assertEqual(all_records, [])

    def test_non_recursive_scanning(self):
        base = Path(self.test_dir)
        sub = base / "sub"
        sub.mkdir()
        (base / "top_level.bin").write_bytes(b"top")
        (sub / "nested.bin").write_bytes(b"nested")

        files_recursive = self.manager.scan_directory(base, recursive=True, show_progress=False)
        files_flat = self.manager.scan_directory(base, recursive=False, show_progress=False)

        self.assertEqual(len(files_recursive), 2)
        self.assertEqual(len(files_flat), 1)
        self.assertEqual(files_flat[0].name, "top_level.bin")


class TestCLIAndInteractiveResolution(unittest.TestCase):
    """Test CLI helpers, summary table output, and interactive resolution flows."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = ApplicationManager(rules_path=None)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_arg_parser_defaults_and_flags(self):
        from app import build_arg_parser
        parser = build_arg_parser()
        args = parser.parse_args(["--dir", "/tmp/apps", "--dry-run", "--chunk-size", "32768", "--log-level", "DEBUG", "--no-progress"])
        self.assertEqual(args.directory, "/tmp/apps")
        self.assertTrue(args.dry_run)
        self.assertEqual(args.chunk_size, 32768)
        self.assertEqual(args.log_level, "DEBUG")
        self.assertFalse(args.show_progress)
        self.assertTrue(args.recursive)

    def test_category_breakdown_table_rendering(self):
        rec1 = FileRecord(path=Path("/tmp/a.py"), size=1000, category="Development")
        rec2 = FileRecord(path=Path("/tmp/b.py"), size=1000, category="Development", sha256_hash="abc")
        rec3 = FileRecord(path=Path("/tmp/c.py"), size=1000, category="Development", sha256_hash="abc")

        duplicates = {"abc": [rec2, rec3]}
        all_records = [rec1, rec2, rec3]

        # Should render cleanly without throwing exceptions
        display_category_breakdown_table(all_records, duplicates, reclaimed_bytes=1000)

    def test_interactive_keep_command(self):
        base = Path(self.test_dir)
        f1 = base / "app_v1.exe"
        f2 = base / "app_v2.exe"
        f1.write_bytes(b"SAME_CONTENT")
        f2.write_bytes(b"SAME_CONTENT")

        duplicates, all_records = self.manager.find_duplicates(base, show_progress=False)
        self.assertEqual(len(duplicates), 1)

        # Simulate user selecting 'keep 1' then confirming 'y'
        with patch("builtins.input", side_effect=["keep 1", "y"]):
            reclaimed = interactive_duplicate_resolution(duplicates, self.manager, all_records, dry_run=False)

        self.assertTrue(f1.exists(), "Instance 1 should be kept")
        self.assertFalse(f2.exists(), "Instance 2 should be deleted")
        self.assertEqual(reclaimed, 12)

    def test_interactive_delete_command(self):
        base = Path(self.test_dir)
        f1 = base / "copy1.bin"
        f2 = base / "copy2.bin"
        f1.write_bytes(b"DATA")
        f2.write_bytes(b"DATA")

        duplicates, all_records = self.manager.find_duplicates(base, show_progress=False)

        # Simulate user selecting 'delete 2' then confirming 'y'
        with patch("builtins.input", side_effect=["delete 2", "y"]):
            reclaimed = interactive_duplicate_resolution(duplicates, self.manager, all_records, dry_run=False)

        self.assertTrue(f1.exists())
        self.assertFalse(f2.exists())
        self.assertEqual(reclaimed, 4)

    def test_interactive_keep_newest_command(self):
        import time
        base = Path(self.test_dir)
        f_old = base / "old.bin"
        f_new = base / "new.bin"
        f_old.write_bytes(b"IDENTICAL")
        time.sleep(0.05)
        f_new.write_bytes(b"IDENTICAL")

        duplicates, all_records = self.manager.find_duplicates(base, show_progress=False)

        with patch("builtins.input", side_effect=["keep-newest", "y"]):
            reclaimed = interactive_duplicate_resolution(duplicates, self.manager, all_records, dry_run=False)

        self.assertTrue(f_new.exists(), "Newest file should be kept")
        self.assertFalse(f_old.exists(), "Oldest file should be removed")
        self.assertEqual(reclaimed, 9)

    def test_interactive_skip_and_abort(self):
        base = Path(self.test_dir)
        f1 = base / "file1.bin"
        f2 = base / "file2.bin"
        f1.write_bytes(b"DATA")
        f2.write_bytes(b"DATA")

        duplicates, all_records = self.manager.find_duplicates(base, show_progress=False)

        # User chooses 'skip'
        with patch("builtins.input", side_effect=["skip"]):
            reclaimed = interactive_duplicate_resolution(duplicates, self.manager, all_records, dry_run=False)

        self.assertTrue(f1.exists())
        self.assertTrue(f2.exists())
        self.assertEqual(reclaimed, 0)

    def test_zero_byte_duplicate_files(self):
        base = Path(self.test_dir)
        z1 = base / "zero1.dat"
        z2 = base / "zero2.dat"
        z1.write_bytes(b"")
        z2.write_bytes(b"")

        duplicates, all_records = self.manager.find_duplicates(base, show_progress=False)
        empty_hash = hashlib.sha256(b"").hexdigest()
        self.assertIn(empty_hash, duplicates)
        self.assertEqual(len(duplicates[empty_hash]), 2)
        self.assertEqual(len(all_records), 2)


if __name__ == "__main__":
    unittest.main()
