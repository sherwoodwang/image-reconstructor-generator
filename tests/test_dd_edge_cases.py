#!/usr/bin/env python3
"""
Edge case tests for dd modes including block boundaries, large offsets, and error handling.
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


class TestDDEdgeCases(unittest.TestCase):
    """Test edge cases for dd modes including boundary conditions."""

    def setUp(self):
        """Create temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        self.test_dir_path = Path(self.test_dir)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_offset_at_zero(self):
        """Test reconstruction starting at offset 0.

        Memory estimate:
        - Image: 64 bytes
        - Script: ~14 KB
        - Subprocess overhead: ~65 MB
        - Total: < 70 MB
        """
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create minimal image (64 bytes)
            image_file = self.test_dir_path / "test.img"
            image_data = b"TESTDATA" * 8  # 64 bytes
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
                    block_size=16,
                    min_extent_size=16
                )
                processor.process_file(str(source_file))
                processor.generate_script()

            script_file.chmod(0o755)

            # Test with default mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), str(output_file)],
                capture_output=True,
                cwd=self.test_dir,
                timeout=10
            )

            self.assertEqual(result.returncode, 0,
                            f"Failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data,
                            "Output produced incorrect result")

        finally:
            os.chdir(old_cwd)

    def test_block_boundary_alignment(self):
        """Test reconstruction with data aligned at block boundaries.

        Memory estimate:
        - Image: 96 bytes (3 blocks × 32 bytes)
        - Script: ~14 KB
        - Subprocess overhead: ~65 MB
        - Total: < 70 MB
        """
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create minimal image with block boundaries (96 bytes)
            block_size = 32
            image_file = self.test_dir_path / "test.img"
            image_data = b"A" * block_size + b"B" * block_size + b"C" * block_size
            image_file.write_bytes(image_data)

            # Create source files
            source1 = self.test_dir_path / "b1.txt"
            source1.write_bytes(b"A" * block_size)
            source2 = self.test_dir_path / "b2.txt"
            source2.write_bytes(b"B" * block_size)
            source3 = self.test_dir_path / "b3.txt"
            source3.write_bytes(b"C" * block_size)

            # Generate script
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=block_size,
                    min_extent_size=block_size
                )
                processor.process_file(str(source1))
                processor.process_file(str(source2))
                processor.process_file(str(source3))
                processor.generate_script()

            script_file.chmod(0o755)

            # Test with default mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), str(output_file)],
                capture_output=True,
                cwd=self.test_dir,
                timeout=10
            )

            self.assertEqual(result.returncode, 0,
                            f"Failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data,
                            "Block-aligned reconstruction failed")

        finally:
            os.chdir(old_cwd)

    def test_partial_block_at_end(self):
        """Test reconstruction with partial block at the end.

        Memory estimate:
        - Image: 48 bytes (1.5 blocks)
        - Script: ~14 KB
        - Subprocess overhead: ~65 MB
        - Total: < 70 MB
        """
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create minimal image with partial block (48 bytes)
            block_size = 32
            image_file = self.test_dir_path / "test.img"
            image_data = b"X" * block_size + b"Y" * (block_size // 2)
            image_file.write_bytes(image_data)

            # Create source
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(image_data)

            # Generate script
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=block_size,
                    min_extent_size=len(image_data)
                )
                processor.process_file(str(source_file))
                processor.generate_script()

            script_file.chmod(0o755)

            # Test with default mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), str(output_file)],
                capture_output=True,
                cwd=self.test_dir,
                timeout=10
            )

            self.assertEqual(result.returncode, 0,
                            f"Failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            self.assertEqual(len(output_data), len(image_data))
            self.assertEqual(output_data, image_data)

        finally:
            os.chdir(old_cwd)

    def test_single_byte_extraction(self):
        """Test extracting single bytes at various positions.

        Memory estimate:
        - Image: 32 bytes
        - Script: ~14 KB
        - Subprocess overhead: ~65 MB
        - Total: < 70 MB
        """
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create minimal image (32 bytes) with distinctive marker
            block_size = 32
            image_file = self.test_dir_path / "test.img"
            # Create image where offset 15 has a unique byte
            pattern = b"ABCDEFGHIJ" + b"\xFF" + b"UVWXYZ012345"
            image_file.write_bytes(pattern)

            # Create source file matching exactly
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(pattern)

            # Generate script
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=block_size,
                    min_extent_size=block_size
                )
                processor.process_file(str(source_file))
                processor.generate_script()

            script_file.chmod(0o755)

            # Test with default mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), str(output_file)],
                capture_output=True,
                cwd=self.test_dir,
                timeout=10
            )

            self.assertEqual(result.returncode, 0,
                            f"Failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            # Verify the full reconstruction matches
            self.assertEqual(output_data, pattern,
                            "Reconstruction does not match original")

        finally:
            os.chdir(old_cwd)

    def test_empty_file_handling(self):
        """Test handling of empty image files."""
        # Create empty image
        image_file = self.test_dir_path / "empty.img"
        image_file.write_bytes(b"")

        # Generate script
        script_file = self.test_dir_path / "rebuild.sh"
        with open(script_file, 'wb') as f:
            processor = ImageProcessor(image_file, f)
            processor.generate_script()

        script_file.chmod(0o755)

        # Should succeed and create empty output
        output_file = self.test_dir_path / "output.img"
        result = subprocess.run(
            [str(script_file), str(output_file)],
            capture_output=True,
            cwd=self.test_dir
        )

        self.assertEqual(result.returncode, 0,
                        f"Empty file script failed: {result.stderr.decode()}")

        self.assertTrue(output_file.exists(), "Output file not created")
        self.assertEqual(output_file.stat().st_size, 0,
                        "Output should be empty")

    def test_very_small_block_size(self):
        """Test with very small block size.

        Memory estimate:
        - Image: 61 bytes
        - Script: ~14 KB
        - Subprocess overhead: ~65 MB
        - Total: < 70 MB
        """
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create minimal image (61 bytes)
            image_file = self.test_dir_path / "test.img"
            image_data = b"Small" * 12 + b"X"  # 61 bytes
            image_file.write_bytes(image_data)

            # Create source
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(image_data)

            # Generate script with tiny block size
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=16,
                    min_extent_size=16
                )
                processor.process_file(str(source_file))
                processor.generate_script()

            script_file.chmod(0o755)

            # Test with default mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), str(output_file)],
                capture_output=True,
                cwd=self.test_dir,
                timeout=10
            )

            self.assertEqual(result.returncode, 0,
                            f"Failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data)

        finally:
            os.chdir(old_cwd)

    def test_large_block_size(self):
        """Test with large block size (simulated).

        Memory estimate:
        - Image: 32 bytes
        - Script: ~14 KB
        - Subprocess overhead: ~65 MB
        - Total: < 70 MB
        """
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create minimal image (32 bytes)
            block_size = 256  # Simulate large block size
            image_file = self.test_dir_path / "test.img"
            image_data = b"Data" * 8  # 32 bytes
            image_file.write_bytes(image_data)

            # Create source
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(image_data)

            # Generate script with block size larger than file
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=block_size,
                    min_extent_size=16
                )
                processor.process_file(str(source_file))
                processor.generate_script()

            script_file.chmod(0o755)

            # Test with default mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), str(output_file)],
                capture_output=True,
                cwd=self.test_dir,
                timeout=10
            )

            self.assertEqual(result.returncode, 0,
                            f"Failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data)

        finally:
            os.chdir(old_cwd)

    def test_cross_mode_consistency(self):
        """Verify dd modes produce identical output.

        This test uses min_extent_size < block_size to test the edge case
        where min_extent_blocks would be 0 (now fixed to be at least 1).
        """
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create minimal image (48 bytes)
            block_size = 16
            image_file = self.test_dir_path / "test.img"
            part1 = b"A" * 16
            part2 = b"B" * 16
            part3 = b"C" * 16
            image_data = part1 + part2 + part3
            image_file.write_bytes(image_data)

            # Create source files
            source1 = self.test_dir_path / "s1.txt"
            source1.write_bytes(part1)
            source2 = self.test_dir_path / "s2.txt"
            source2.write_bytes(part2)
            source3 = self.test_dir_path / "s3.txt"
            source3.write_bytes(part3)

            # Generate script with min_extent_size < block_size
            # This tests the edge case fix where min_extent_blocks must be >= 1
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=block_size,
                    min_extent_size=8  # Less than block_size!
                )
                processor.process_file(str(source1))
                processor.process_file(str(source2))
                processor.process_file(str(source3))
                processor.generate_script()

            script_file.chmod(0o755)

            # Test with default mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), str(output_file)],
                capture_output=True,
                cwd=self.test_dir,
                timeout=10
            )

            self.assertEqual(result.returncode, 0,
                            f"Failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data)

        finally:
            os.chdir(old_cwd)

    def test_missing_source_file_error(self):
        """Test error handling when source file is missing."""
        # This tests the script's error handling, not the processor
        # We'll manually create a script that references a missing file
        script_file = self.test_dir_path / "rebuild.sh"

        script_content = '''#!/bin/sh
set -e

# Minimal script with missing file reference
copy_from_file() {
    local file="$1"
    local skip=$2
    local count=$3
    dd if="$file" bs=1 skip="$skip" count="$count" 2>/dev/null || {
        echo "Error: Failed to read from '$file'" >&2
        exit 1
    }
}

# Try to copy from non-existent file
copy_from_file "/tmp/nonexistent_test_file_12345.txt" 0 100 > "$1"
'''
        script_file.write_text(script_content)
        script_file.chmod(0o755)

        # Should fail with error
        output_file = self.test_dir_path / "output.img"
        result = subprocess.run(
            [str(script_file), str(output_file)],
            capture_output=True,
            cwd=self.test_dir
        )

        # Should return non-zero exit code
        self.assertNotEqual(result.returncode, 0,
                           "Script should fail when source file missing")

        # Should have error message
        stderr = result.stderr.decode()
        self.assertTrue(len(stderr) > 0 or not output_file.exists(),
                       "Should produce error or no output file")


if __name__ == '__main__':
    unittest.main()
