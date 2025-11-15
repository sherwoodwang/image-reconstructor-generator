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
        """Test reconstruction starting at offset 0."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create image with known data
            image_file = self.test_dir_path / "test.img"
            image_data = b"ABCDEFGH" * 64  # 512 bytes
            image_file.write_bytes(image_data)

            # Create source file
            source_file = self.test_dir_path / "source.txt"
            source_file.write_bytes(b"ABCDEFGH" * 64)

            # Generate script
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=512,
                    min_extent_size=256
                )
                processor.begin()
                processor.process_file(str(source_file))
                processor.finalize()

            script_file.chmod(0o755)

            # Test all three modes
            for mode in [None, 'plain-dd', 'no-dd']:
                output_file = self.test_dir_path / f"output_{mode or 'auto'}.img"

                cmd = [str(script_file)]
                if mode:
                    cmd.extend(['-x', mode])
                cmd.append(str(output_file))

                result = subprocess.run(cmd, capture_output=True, cwd=self.test_dir)

                self.assertEqual(result.returncode, 0,
                                f"Mode {mode} failed: {result.stderr.decode()}")

                output_data = output_file.read_bytes()
                self.assertEqual(output_data, image_data,
                                f"Mode {mode} produced incorrect output")

        finally:
            os.chdir(old_cwd)

    def test_block_boundary_alignment(self):
        """Test reconstruction with data aligned at block boundaries."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create image with data at exact block boundaries
            block_size = 4096
            image_file = self.test_dir_path / "test.img"
            # First block: A's, Second block: B's, Third block: C's
            image_data = (b"A" * block_size +
                         b"B" * block_size +
                         b"C" * block_size)
            image_file.write_bytes(image_data)

            # Create source files matching each block
            source1 = self.test_dir_path / "block1.txt"
            source1.write_bytes(b"A" * block_size)

            source2 = self.test_dir_path / "block2.txt"
            source2.write_bytes(b"B" * block_size)

            source3 = self.test_dir_path / "block3.txt"
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
                processor.begin()
                processor.process_file(str(source1))
                processor.process_file(str(source2))
                processor.process_file(str(source3))
                processor.finalize()

            script_file.chmod(0o755)

            # Test with plain-dd mode (most affected by boundary optimization)
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), '-x', 'plain-dd', str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            self.assertEqual(result.returncode, 0,
                            f"Script failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data,
                            "Block-aligned reconstruction failed")

        finally:
            os.chdir(old_cwd)

    def test_partial_block_at_end(self):
        """Test reconstruction with partial block at the end."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create image that doesn't align to block boundary
            block_size = 4096
            image_file = self.test_dir_path / "test.img"
            # 1.5 blocks
            image_data = b"X" * block_size + b"Y" * (block_size // 2)
            image_file.write_bytes(image_data)

            # Create matching source
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
                processor.begin()
                processor.process_file(str(source_file))
                processor.finalize()

            script_file.chmod(0o755)

            # Test all modes
            for mode in ['gnu-dd', 'plain-dd', 'no-dd']:
                output_file = self.test_dir_path / f"output_{mode}.img"
                result = subprocess.run(
                    [str(script_file), '-x', mode, str(output_file)],
                    capture_output=True,
                    cwd=self.test_dir
                )

                self.assertEqual(result.returncode, 0,
                                f"Mode {mode} failed: {result.stderr.decode()}")

                output_data = output_file.read_bytes()
                self.assertEqual(len(output_data), len(image_data),
                                f"Mode {mode} produced wrong size")
                self.assertEqual(output_data, image_data,
                                f"Mode {mode} produced incorrect data")

        finally:
            os.chdir(old_cwd)

    def test_single_byte_extraction(self):
        """Test extracting single bytes at various positions."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create image with pattern
            block_size = 512
            image_file = self.test_dir_path / "test.img"
            # Pattern that's easy to verify
            pattern = bytes(range(256)) + bytes(range(256))
            image_file.write_bytes(pattern)

            # Create source with single unique byte
            source_file = self.test_dir_path / "marker.txt"
            source_file.write_bytes(b"\xFF")

            # Generate script that places marker at offset 100
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=block_size,
                    min_extent_size=9999  # Force no matching
                )
                processor.begin()
                # Write first 100 bytes from image
                processor.output.write(pattern[:100])
                # Now process the marker file
                processor.process_file(str(source_file))
                # Write rest
                processor.output.write(pattern[101:])
                processor.finalize()

            script_file.chmod(0o755)

            # Test with plain-dd mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), '-x', 'plain-dd', str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            self.assertEqual(result.returncode, 0,
                            f"Script failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            # Verify the marker is at position 100
            self.assertEqual(output_data[100], 0xFF,
                            "Single byte marker not at correct position")

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
            processor.begin()
            processor.finalize()

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
        """Test with very small block size (512 bytes)."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create small image
            image_file = self.test_dir_path / "test.img"
            image_data = b"Small" * 200  # 1000 bytes
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
                    block_size=512,
                    min_extent_size=500
                )
                processor.begin()
                processor.process_file(str(source_file))
                processor.finalize()

            script_file.chmod(0o755)

            # Test with plain-dd mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), '-x', 'plain-dd', str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            self.assertEqual(result.returncode, 0,
                            f"Small block size failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data,
                            "Small block size reconstruction incorrect")

        finally:
            os.chdir(old_cwd)

    def test_large_block_size(self):
        """Test with large block size (64 MiB simulated)."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create image smaller than block size
            block_size = 1024 * 1024  # 1 MiB (simulating larger)
            image_file = self.test_dir_path / "test.img"
            image_data = b"Data" * 256  # 1024 bytes
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
                    min_extent_size=512
                )
                processor.begin()
                processor.process_file(str(source_file))
                processor.finalize()

            script_file.chmod(0o755)

            # Test with plain-dd mode
            output_file = self.test_dir_path / "output.img"
            result = subprocess.run(
                [str(script_file), '-x', 'plain-dd', str(output_file)],
                capture_output=True,
                cwd=self.test_dir
            )

            self.assertEqual(result.returncode, 0,
                            f"Large block size failed: {result.stderr.decode()}")

            output_data = output_file.read_bytes()
            self.assertEqual(output_data, image_data,
                            "Large block size reconstruction incorrect")

        finally:
            os.chdir(old_cwd)

    def test_cross_mode_consistency(self):
        """Verify all three dd modes produce identical output."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)

            # Create complex image with mixed content
            block_size = 4096
            image_file = self.test_dir_path / "test.img"
            part1 = b"A" * 1000
            part2 = b"B" * 3000
            part3 = b"C" * 2048
            image_data = part1 + part2 + part3
            image_file.write_bytes(image_data)

            # Create source files
            source1 = self.test_dir_path / "s1.txt"
            source1.write_bytes(part1)
            source2 = self.test_dir_path / "s2.txt"
            source2.write_bytes(part2)
            source3 = self.test_dir_path / "s3.txt"
            source3.write_bytes(part3)

            # Generate script
            script_file = self.test_dir_path / "rebuild.sh"
            with open(script_file, 'wb') as f:
                processor = ImageProcessor(
                    image_file,
                    f,
                    block_size=block_size,
                    min_extent_size=500
                )
                processor.begin()
                processor.process_file(str(source1))
                processor.process_file(str(source2))
                processor.process_file(str(source3))
                processor.finalize()

            script_file.chmod(0o755)

            # Run with all three modes
            outputs = {}
            for mode in ['gnu-dd', 'plain-dd', 'no-dd']:
                output_file = self.test_dir_path / f"output_{mode}.img"
                result = subprocess.run(
                    [str(script_file), '-x', mode, str(output_file)],
                    capture_output=True,
                    cwd=self.test_dir
                )

                self.assertEqual(result.returncode, 0,
                                f"Mode {mode} failed: {result.stderr.decode()}")

                outputs[mode] = output_file.read_bytes()

            # Verify all outputs are identical
            gnu_output = outputs['gnu-dd']
            plain_output = outputs['plain-dd']
            no_dd_output = outputs['no-dd']

            self.assertEqual(gnu_output, image_data,
                            "GNU dd mode output incorrect")
            self.assertEqual(plain_output, image_data,
                            "Plain dd mode output incorrect")
            self.assertEqual(no_dd_output, image_data,
                            "No-dd mode output incorrect")

            # Verify cross-mode consistency
            self.assertEqual(gnu_output, plain_output,
                            "GNU and plain-dd outputs differ")
            self.assertEqual(plain_output, no_dd_output,
                            "Plain and no-dd outputs differ")

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
