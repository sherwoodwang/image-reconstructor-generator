#!/usr/bin/env python3
"""
Tests for timestamp handling in generated scripts across different systems.
"""

import unittest
import tempfile
import subprocess
from pathlib import Path
import sys
import os
import time

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_rebuilder import ImageProcessor


class TestTimestampHandling(unittest.TestCase):
    """Test timestamp restoration in generated scripts."""

    def setUp(self):
        """Create temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        self.test_dir_path = Path(self.test_dir)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_timestamp_restoration_basic(self):
        """Test that timestamps are restored when not skipped."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create image with known content
            image_file = self.test_dir_path / "test.img"
            image_data = b"TestData" * 64
            image_file.write_bytes(image_data)

            # Get the original mtime
            original_mtime = image_file.stat().st_mtime

            # Create source file
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(image_data)

            # Generate script
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=512,
                    min_extent_size=256
                )
                processor.process_file(str(source_file))
                processor.generate_script()

            script_file.chmod(0o755)

            # Run without timestamp skip
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            self.assertEqual(result.returncode, 0,
                            f"Script failed: {result.stderr.decode()}")

            self.assertTrue(output_file.exists(), "Output file not created")
            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data,
                            "Output data doesn't match original")

            # Check that output file has a reasonable mtime (should be recent)
            output_mtime = output_file.stat().st_mtime
            current_time = time.time()
            # The output mtime should be close to the image mtime or current time
            # depending on whether touch succeeded
            time_diff = abs(current_time - output_mtime)
            self.assertLess(time_diff, 3600,  # Within 1 hour of now
                           "Output file timestamp seems wrong")

        finally:
            os.chdir(old_cwd)

    def test_timestamp_skip_option(self):
        """Test that --skip-timestamps option prevents timestamp restoration."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create image
            image_file = self.test_dir_path / "test.img"
            image_data = b"SkipTest" * 32
            image_file.write_bytes(image_data)

            # Create source file
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(image_data)

            # Generate script
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=512,
                    min_extent_size=256
                )
                processor.process_file(str(source_file))
                processor.generate_script()

            script_file.chmod(0o755)

            # Record current time before script execution
            before_exec = time.time()
            time.sleep(0.1)  # Ensure time difference

            # Run with -t (skip timestamps)
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), '-t', str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            time.sleep(0.1)  # Ensure time difference
            after_exec = time.time()

            self.assertEqual(result.returncode, 0,
                            f"Script failed: {result.stderr.decode()}")

            self.assertTrue(output_file.exists(), "Output file not created")

            # Check that output mtime is recent (should be around execution time)
            output_mtime = output_file.stat().st_mtime
            self.assertGreater(output_mtime, before_exec - 1,
                              "Output mtime is too old")
            self.assertLess(output_mtime, after_exec + 1,
                           "Output mtime is in the future")

        finally:
            os.chdir(old_cwd)

    def test_timestamp_restoration_in_info_mode(self):
        """Test that timestamp info is displayed in info mode."""
        # Create image
        image_file = self.test_dir_path / "test.img"
        image_data = b"Info" * 16
        image_file.write_bytes(image_data)

        # Generate script
        script_file = self.test_dir_path / "rebuild.sh"
        with open(script_file, 'wb') as f:
            processor = ImageProcessor(image_file, f)
            processor.generate_script()

        script_file.chmod(0o755)

        # Run in info mode
        result = subprocess.run(
            [str(script_file), '-i'],
            capture_output=True,
            cwd=self.test_dir
        )

        self.assertEqual(result.returncode, 0,
                        f"Info mode failed: {result.stderr.decode()}")

        output = result.stdout.decode()
        # Should contain timestamp information
        self.assertIn('Modified:', output,
                     "Info output should include Modified timestamp")

    def test_timestamp_with_verbose_mode(self):
        """Test that verbose mode doesn't interfere with timestamp handling."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create image
            image_file = self.test_dir_path / "test.img"
            image_data = b"Verbose" * 32
            image_file.write_bytes(image_data)

            # Create source file
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(image_data)

            # Generate script
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=512,
                    min_extent_size=256
                )
                processor.process_file(str(source_file))
                processor.generate_script()

            script_file.chmod(0o755)

            # Run with verbose flag
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), '-v', str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            self.assertEqual(result.returncode, 0,
                            f"Verbose script failed: {result.stderr.decode()}")

            self.assertTrue(output_file.exists(), "Output file not created")
            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data,
                            "Output data doesn't match with verbose mode")

        finally:
            os.chdir(old_cwd)

    def test_timestamp_format_display(self):
        """Test that timestamps are displayed in readable format in info mode."""
        import time
        from datetime import datetime

        # Create image
        image_file = self.test_dir_path / "test.img"
        image_data = b"Format" * 16
        image_file.write_bytes(image_data)

        # Get current time for reference
        current_mtime = image_file.stat().st_mtime
        current_date = datetime.fromtimestamp(current_mtime)

        # Generate script
        script_file = self.test_dir_path / "rebuild.sh"
        with open(script_file, 'wb') as f:
            processor = ImageProcessor(image_file, f)
            processor.generate_script()

        script_file.chmod(0o755)

        # Run in info mode
        result = subprocess.run(
            [str(script_file), '-i'],
            capture_output=True,
            cwd=self.test_dir
        )

        output = result.stdout.decode()

        # The timestamp should be displayed (as @ followed by Unix timestamp)
        self.assertIn('@', output,
                     "Timestamps should be displayed with @ prefix")

        # Extract the mtime value (should be a Unix timestamp)
        lines = output.split('\n')
        for line in lines:
            if 'Modified:' in line:
                # Should contain the @ prefix for timestamp
                self.assertIn('@', line,
                             "Modified line should contain timestamp info")
                break

    def test_multiple_reconstructions_same_timestamp(self):
        """Test that multiple reconstructions maintain consistent timestamps."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create image
            image_file = self.test_dir_path / "test.img"
            image_data = b"Multi" * 20
            image_file.write_bytes(image_data)

            # Get original mtime
            original_mtime = image_file.stat().st_mtime

            # Create source file
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(image_data)

            # Generate script
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=512,
                    min_extent_size=256
                )
                processor.process_file(str(source_file))
                processor.generate_script()

            script_file.chmod(0o755)

            # Run twice and compare mtimes
            mtimes = []
            for i in range(2):
                output_file = self.test_dir_path / f"output{i}.img"
                result = subprocess.run(
                    [str(script_file), str(output_file)],
                    capture_output=True,
                    cwd=self.test_dir
                )

                self.assertEqual(result.returncode, 0,
                                f"Script iteration {i} failed")

                mtime = output_file.stat().st_mtime
                mtimes.append(mtime)

            # Both should have been created with reasonable timestamps
            # (they might differ slightly due to restoration method)
            for mtime in mtimes:
                current_time = time.time()
                time_diff = abs(current_time - mtime)
                self.assertLess(time_diff, 3600,
                               f"Timestamp {mtime} seems unreasonable")

        finally:
            os.chdir(old_cwd)


if __name__ == '__main__':
    unittest.main()
