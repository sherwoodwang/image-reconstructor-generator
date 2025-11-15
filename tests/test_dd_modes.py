#!/usr/bin/env python3
"""
Tests for different dd execution modes (GNU vs plain/BSD).
"""

import unittest
import tempfile
import subprocess
from pathlib import Path
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_rebuilder import ImageProcessor


class TestDDModes(unittest.TestCase):
    """Test script generation and execution with different dd modes."""

    def setUp(self):
        """Create temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        self.test_dir_path = Path(self.test_dir)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_script_with_gnu_dd_mode(self):
        """Test script execution with GNU dd mode (default on Linux)."""
        # Save current directory
        old_cwd = os.getcwd()

        try:
            # Change to test directory
            os.chdir(self.test_dir)

            # Create test image (very small to avoid timeout)
            image_file = self.test_dir_path / "test.img"
            image_data = b"X" * 512  # 512 bytes only
            image_file.write_bytes(image_data)

            # Create test source file (minimal)
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(b"test")

            # Generate script (skip extent matching for speed)
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=512,
                    min_extent_size=10000000  # Huge min size to skip matching
                )
                processor.begin()
                processor.process_file(str(source_file))
                processor.finalize()

            # Make script executable
            script_file.chmod(0o755)

            # Run reconstruction (will use GNU dd if available)
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            # Verify success
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr.decode()}")

            # Verify output matches original
            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data, "Reconstructed image doesn't match original")

        finally:
            # Restore directory
            os.chdir(old_cwd)

    def test_script_with_plain_dd_mode(self):
        """Test script execution with plain dd mode (forced with -x plain-dd)."""
        # Save current directory
        old_cwd = os.getcwd()

        try:
            # Change to test directory
            os.chdir(self.test_dir)

            # Create test image (very small to avoid timeout)
            image_file = self.test_dir_path / "test.img"
            image_data = b"Y" * 256  # 256 bytes only
            image_file.write_bytes(image_data)

            # Create test source file (minimal)
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(b"test")

            # Generate script (skip extent matching for speed)
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=512,
                    min_extent_size=10000000  # Huge min size to skip matching
                )
                processor.begin()
                processor.process_file(str(source_file))
                processor.finalize()

            # Make script executable
            script_file.chmod(0o755)

            # Run reconstruction with -x plain-dd to force BSD-style mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), '-x', 'plain-dd', str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            # Verify success
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr.decode()}")

            # Verify output matches original
            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data, "Reconstructed image doesn't match original (plain-dd mode)")

        finally:
            # Restore directory
            os.chdir(old_cwd)

    def test_script_verbose_shows_correct_commands(self):
        """Test that verbose mode shows the correct commands for each dd mode."""
        # Create test image
        image_file = self.test_dir_path / "test.img"
        image_data = b"X" * 1000
        image_file.write_bytes(image_data)

        # Generate script
        script_file = self.test_dir_path / "rebuild.sh"
        with open(script_file, 'wb') as f:
            processor = ImageProcessor(
                image_file,
                f,
                block_size=4096,
                min_extent_size=512
            )
            processor.begin()
            processor.finalize()

        # Make script executable
        script_file.chmod(0o755)

        # Run with verbose in GNU dd mode
        output_file = self.test_dir_path / "output1.img"
        result_gnu = subprocess.run(
            [str(script_file), '-v', str(output_file)],
            capture_output=True,
            cwd=self.test_dir
        )

        self.assertEqual(result_gnu.returncode, 0, "GNU dd mode failed")
        stderr_gnu = result_gnu.stderr.decode()

        # Run with verbose in plain dd mode
        output_file2 = self.test_dir_path / "output2.img"
        result_plain = subprocess.run(
            [str(script_file), '-v', '-x', 'plain-dd', str(output_file2)],
            capture_output=True,
            cwd=self.test_dir
        )

        self.assertEqual(result_plain.returncode, 0, "Plain dd mode failed")
        stderr_plain = result_plain.stderr.decode()

        # Check that GNU mode shows iflag (if GNU dd is available)
        if 'iflag' in stderr_gnu:
            self.assertIn('iflag=skip_bytes,count_bytes', stderr_gnu,
                         "GNU dd mode should show iflag")
        
        # Check that plain mode shows tail/head
        self.assertIn('tail -c', stderr_plain,
                     "Plain dd mode should show tail command")
        self.assertIn('head -c', stderr_plain,
                     "Plain dd mode should show head command")

    def test_plain_dd_option_parsing(self):
        """Test that -x option correctly parses plain-dd."""
        # Create test image
        image_file = self.test_dir_path / "test.img"
        image_file.write_bytes(b"test")

        # Generate script
        script_file = self.test_dir_path / "rebuild.sh"
        with open(script_file, 'wb') as f:
            processor = ImageProcessor(image_file, f)
            processor.begin()
            processor.finalize()

        # Make script executable
        script_file.chmod(0o755)

        # Test -x plain-dd option
        result = subprocess.run(
            [str(script_file), '-x', 'plain-dd', '-i'],
            capture_output=True,
            cwd=self.test_dir
        )

        # Should succeed (info mode)
        self.assertEqual(result.returncode, 0,
                        f"Script with -x plain-dd failed: {result.stderr.decode()}")

    def test_script_with_no_dd_mode(self):
        """Test script execution with no-dd mode (forced with -x no-dd)."""
        # Save current directory
        old_cwd = os.getcwd()

        try:
            # Change to test directory
            os.chdir(self.test_dir)

            # Create test image (very small to avoid timeout)
            image_file = self.test_dir_path / "test.img"
            image_data = b"Z" * 128  # 128 bytes only
            image_file.write_bytes(image_data)

            # Create test source file (minimal)
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(b"test")

            # Generate script (skip extent matching for speed)
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=512,
                    min_extent_size=10000000  # Huge min size to skip matching
                )
                processor.begin()
                processor.process_file(str(source_file))
                processor.finalize()

            # Make script executable
            script_file.chmod(0o755)

            # Run reconstruction with -x no-dd to force no-dd mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), '-x', 'no-dd', str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            # Verify success
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr.decode()}")

            # Verify output matches original
            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data, "Reconstructed image doesn't match original (no-dd mode)")

        finally:
            # Restore directory
            os.chdir(old_cwd)


if __name__ == '__main__':
    unittest.main()
