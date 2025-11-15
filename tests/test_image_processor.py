#!/usr/bin/env python3
"""
Tests for the ImageProcessor class initialization and basic methods.
"""

import unittest
import tempfile
import sys
from pathlib import Path
from io import BytesIO

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_rebuilder import ImageProcessor


class TestImageProcessor(unittest.TestCase):
    """Tests for the ImageProcessor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.image_file = Path(self.temp_dir) / "test.img"
        self.image_file.touch()
        self.output = BytesIO()
        self.original_cwd = Path.cwd()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_init(self):
        """Test ImageProcessor initialization."""
        processor = ImageProcessor(self.image_file, self.output)

        self.assertEqual(processor.image_file, self.image_file)
        self.assertEqual(processor.output_stream, self.output)

    def test_begin_callable(self):
        """Test that begin() method is callable."""
        processor = ImageProcessor(self.image_file, self.output)

        # Should not raise an error
        processor.begin()

    def test_process_file_callable(self):
        """Test that process_file() method is callable."""
        processor = ImageProcessor(self.image_file, self.output)

        # Create a test file to process
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"test content")

        # Change to temp directory so files are within working directory
        import os
        os.chdir(self.temp_dir)
        try:
            # Should not raise an error
            processor.process_file(str(test_file.relative_to(self.temp_dir)))
        finally:
            os.chdir(self.original_cwd)

    def test_process_file_path_security_escaping_paths(self):
        """Test that paths trying to escape working directory are rejected."""
        processor = ImageProcessor(self.image_file, self.output)

        # Create a test file outside the temp directory
        outside_file = Path(self.temp_dir).parent / "outside.txt"
        outside_file.write_bytes(b"outside content")

        # Change to temp directory
        import os
        os.chdir(self.temp_dir)
        try:
            # These should all raise ValueError for escaping working directory
            with self.assertRaises(ValueError) as cm:
                processor.process_file("../outside.txt")
            self.assertIn("working directory", str(cm.exception))

            with self.assertRaises(ValueError) as cm:
                processor.process_file("../../outside.txt")
            self.assertIn("working directory", str(cm.exception))

            with self.assertRaises(ValueError) as cm:
                processor.process_file("../../../etc/passwd")
            self.assertIn("working directory", str(cm.exception))

        finally:
            os.chdir(self.original_cwd)
            outside_file.unlink(missing_ok=True)

    def test_process_file_path_security_dot_dot_components(self):
        """Test that paths with .. components are properly handled and normalized."""
        processor = ImageProcessor(self.image_file, self.output)

        # Create a nested directory structure
        subdir = Path(self.temp_dir) / "subdir"
        subdir.mkdir()
        test_file = subdir / "test.txt"
        test_file.write_bytes(b"test content")

        # Change to temp directory
        import os
        os.chdir(self.temp_dir)
        try:
            # Test cases that should work and be normalized
            test_cases = [
                ("subdir/../subdir/test.txt", "subdir/test.txt"),  # .. that resolves within working directory
                ("subdir/test.txt/../test.txt", "subdir/test.txt"),  # .. that resolves to same file
            ]

            for input_path, expected_normalized in test_cases:
                processor.matches = []  # Reset matches for each test
                processor.process_file(input_path)

                # Verify the path was stored in normalized form
                if processor.matches:  # Only check if matches were found
                    stored_path = processor.matches[0][0]  # First match tuple's path
                    self.assertEqual(str(stored_path), expected_normalized,
                                   f"Path {input_path} should be normalized to {expected_normalized}, got {stored_path}")
                    # Ensure no .. components in stored path
                    self.assertNotIn("..", stored_path.parts,
                                   f"Stored path {stored_path} should not contain .. components")

            # This should fail - .. that escapes working directory
            with self.assertRaises(ValueError) as cm:
                processor.process_file("subdir/../../../etc/passwd")
            self.assertIn("working directory", str(cm.exception))

        finally:
            os.chdir(self.original_cwd)

    def test_process_file_path_security_path_anomalies(self):
        """Test that paths with //, ., and other anomalies are handled and normalized."""
        processor = ImageProcessor(self.image_file, self.output)

        # Create test files
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"test content")

        # Change to temp directory
        import os
        os.chdir(self.temp_dir)
        try:
            # Clear any previous matches
            processor.matches = []

            # Test various path anomalies that should normalize correctly
            test_cases = [
                ("test.txt", "test.txt"),  # Normal path
                ("./test.txt", "test.txt"),  # Current directory
                ("test.txt/.", "test.txt"),  # With trailing .
                ("test.txt//", "test.txt"),  # With double slash
                (".//test.txt", "test.txt"),  # Leading .//
                ("././test.txt", "test.txt"),  # Multiple ./
            ]

            for input_path, expected_normalized in test_cases:
                processor.matches = []  # Reset matches for each test
                processor.process_file(input_path)

                # Verify the path was stored in normalized form
                if processor.matches:  # Only check if matches were found
                    stored_path = processor.matches[0][0]  # First match tuple's path
                    self.assertEqual(str(stored_path), expected_normalized,
                                   f"Path {input_path} should be normalized to {expected_normalized}, got {stored_path}")
                    # Ensure no .. components in stored path
                    self.assertNotIn("..", stored_path.parts,
                                   f"Stored path {stored_path} should not contain .. components")

        finally:
            os.chdir(self.original_cwd)

    def test_process_file_path_security_absolute_paths(self):
        """Test absolute paths within and outside working directory."""
        processor = ImageProcessor(self.image_file, self.output)

        # Create test files
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"test content")

        # Create a file outside temp directory
        outside_file = Path(self.temp_dir).parent / "outside.txt"
        outside_file.write_bytes(b"outside content")

        # Change to temp directory
        import os
        os.chdir(self.temp_dir)
        try:
            # Absolute path within working directory should work and be normalized to relative
            processor.matches = []  # Reset matches
            abs_path = str(test_file.resolve())
            processor.process_file(abs_path)

            # Verify the path was stored as relative, not absolute
            if processor.matches:  # Only check if matches were found
                stored_path = processor.matches[0][0]  # First match tuple's path
                self.assertEqual(str(stored_path), "test.txt",
                               f"Absolute path {abs_path} should be stored as relative 'test.txt', got {stored_path}")
                # Ensure no .. components and it's relative
                self.assertNotIn("..", stored_path.parts,
                               f"Stored path {stored_path} should not contain .. components")
                self.assertFalse(stored_path.is_absolute(),
                               f"Stored path {stored_path} should be relative, not absolute")

            # Absolute path outside working directory should fail
            abs_outside = str(outside_file.resolve())
            with self.assertRaises(ValueError) as cm:
                processor.process_file(abs_outside)
            self.assertIn("working directory", str(cm.exception))

        finally:
            os.chdir(self.original_cwd)
            outside_file.unlink(missing_ok=True)

    def test_process_file_path_security_symlinks(self):
        """Test that symlinks within working directory are allowed and normalized."""
        processor = ImageProcessor(self.image_file, self.output)

        # Create a test file
        test_file = Path(self.temp_dir) / "real_file.txt"
        test_file.write_bytes(b"real content")

        # Create a symlink within the temp directory
        symlink_file = Path(self.temp_dir) / "symlink.txt"
        symlink_file.symlink_to(test_file)

        # Change to temp directory
        import os
        os.chdir(self.temp_dir)
        try:
            # Symlink within working directory should work
            processor.matches = []  # Reset matches
            processor.process_file("symlink.txt")

            # Verify the symlink path was stored in normalized form
            if processor.matches:  # Only check if matches were found
                stored_path = processor.matches[0][0]  # First match tuple's path
                self.assertEqual(str(stored_path), "symlink.txt",
                               f"Symlink path should be stored as 'symlink.txt', got {stored_path}")
                # Ensure no .. components in stored path
                self.assertNotIn("..", stored_path.parts,
                               f"Stored path {stored_path} should not contain .. components")

        finally:
            os.chdir(self.original_cwd)

    def test_process_file_path_security_nonexistent_files(self):
        """Test that nonexistent files are properly rejected."""
        processor = ImageProcessor(self.image_file, self.output)

        # Change to temp directory
        import os
        os.chdir(self.temp_dir)
        try:
            # Nonexistent file should raise FileNotFoundError
            with self.assertRaises(FileNotFoundError):
                processor.process_file("nonexistent.txt")

            # Path that exists but is not a file should raise ValueError
            subdir = Path(self.temp_dir) / "subdir"
            subdir.mkdir()
            with self.assertRaises(ValueError) as cm:
                processor.process_file("subdir")
            self.assertIn("not a file", str(cm.exception))

        finally:
            os.chdir(self.original_cwd)

    def test_finalize_callable(self):
        """Test that finalize() method is callable."""
        processor = ImageProcessor(self.image_file, self.output)

        # Should not raise an error
        processor.finalize()


if __name__ == '__main__':
    unittest.main()
