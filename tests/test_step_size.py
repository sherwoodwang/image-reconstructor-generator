#!/usr/bin/env python3
"""
Tests for step size functionality in extent discovery.
"""

import unittest
import tempfile
import sys
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_reconstructor_generator import ImageProcessor, main


class TestStepSize(unittest.TestCase):
    """Tests for step size parameter in ImageProcessor."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_file = Path(self.temp_dir.name) / "test.img"

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_default_step_size(self):
        """Test that default step size equals min_extent_size."""
        self.image_file.write_bytes(b"A" * 5000)
        processor = ImageProcessor(self.image_file)

        # Default min_extent_size is 1048576 bytes
        self.assertEqual(processor.step_size, 1048576)
        self.assertEqual(processor.step_size, processor.min_extent_size)

    def test_custom_step_size(self):
        """Test that custom step size is applied."""
        self.image_file.write_bytes(b"A" * 5000)
        processor = ImageProcessor(
            self.image_file,
            step_size=262144
        )

        self.assertEqual(processor.step_size, 262144)

    def test_step_size_calculation_to_blocks(self):
        """Test that step_size is correctly converted to step_blocks."""
        self.image_file.write_bytes(b"A" * 5000)
        block_size = 4096
        step_size = 8192

        processor = ImageProcessor(
            self.image_file,
            block_size=block_size,
            step_size=step_size
        )

        expected_blocks = step_size // block_size
        self.assertEqual(processor.step_blocks, expected_blocks)
        self.assertEqual(processor.step_blocks, 2)

    def test_step_size_minimum_one_block(self):
        """Test that step_blocks is at least 1."""
        self.image_file.write_bytes(b"A" * 5000)
        processor = ImageProcessor(
            self.image_file,
            block_size=4096,
            step_size=1  # Very small, but should enforce minimum
        )

        # step_blocks should be max(1, 1 // 4096) = 1
        self.assertGreaterEqual(processor.step_blocks, 1)

    def test_step_size_with_custom_block_size(self):
        """Test step_size calculation with custom block size."""
        self.image_file.write_bytes(b"A" * 5000)
        block_size = 2048
        step_size = 6144

        processor = ImageProcessor(
            self.image_file,
            block_size=block_size,
            step_size=step_size
        )

        expected_blocks = step_size // block_size
        self.assertEqual(processor.step_blocks, expected_blocks)
        self.assertEqual(processor.step_blocks, 3)

    def test_step_size_smaller_than_min_extent_size(self):
        """Test that step_size can be smaller than min_extent_size."""
        self.image_file.write_bytes(b"A" * 5000)
        min_extent_size = 1048576  # 1 MiB
        step_size = 262144  # 256 KiB

        processor = ImageProcessor(
            self.image_file,
            min_extent_size=min_extent_size,
            step_size=step_size
        )

        self.assertEqual(processor.min_extent_size, min_extent_size)
        self.assertEqual(processor.step_size, step_size)
        self.assertLess(processor.step_size, processor.min_extent_size)

    def test_step_size_larger_than_min_extent_size(self):
        """Test that step_size can be larger than min_extent_size."""
        self.image_file.write_bytes(b"A" * 5000)
        min_extent_size = 262144  # 256 KiB
        step_size = 1048576  # 1 MiB

        processor = ImageProcessor(
            self.image_file,
            min_extent_size=min_extent_size,
            step_size=step_size
        )

        self.assertEqual(processor.min_extent_size, min_extent_size)
        self.assertEqual(processor.step_size, step_size)
        self.assertGreater(processor.step_size, processor.min_extent_size)

    def test_step_size_equal_to_min_extent_size(self):
        """Test that step_size can equal min_extent_size."""
        self.image_file.write_bytes(b"A" * 5000)
        size = 524288  # 512 KiB

        processor = ImageProcessor(
            self.image_file,
            min_extent_size=size,
            step_size=size
        )

        self.assertEqual(processor.min_extent_size, size)
        self.assertEqual(processor.step_size, size)
        self.assertEqual(processor.step_blocks, processor.min_extent_blocks)


class TestStepSizeArgumentParsing(unittest.TestCase):
    """Tests for step size command-line argument parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_file = Path(self.temp_dir.name) / "test.img"
        self.image_file.write_bytes(b"A" * 5000)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    @patch('image_reconstructor_generator.ImageProcessor')
    def test_step_size_long_argument(self, mock_processor_class):
        """Test that --step-size argument is properly parsed."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        with patch('sys.argv', [
            'image_reconstructor_generator.py',
            str(self.image_file),
            '--step-size', '262144'
        ]):
            with patch('sys.stdin', StringIO("")):
                with patch('sys.stderr', StringIO()):
                    with patch('sys.stdout') as mock_stdout:
                        mock_stdout.isatty.return_value = False
                        main()

                    # Verify ImageProcessor was called with step_size=262144
                    call_args = mock_processor_class.call_args
                    self.assertEqual(call_args.kwargs['step_size'], 262144)

    @patch('image_reconstructor_generator.ImageProcessor')
    def test_step_size_short_argument(self, mock_processor_class):
        """Test that -s argument works for step size."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        with patch('sys.argv', [
            'image_reconstructor_generator.py',
            str(self.image_file),
            '-s', '524288'
        ]):
            with patch('sys.stdin', StringIO("")):
                with patch('sys.stderr', StringIO()):
                    with patch('sys.stdout') as mock_stdout:
                        mock_stdout.isatty.return_value = False
                        main()

                    # Verify ImageProcessor was called with step_size=524288
                    call_args = mock_processor_class.call_args
                    self.assertEqual(call_args.kwargs['step_size'], 524288)

    @patch('image_reconstructor_generator.ImageProcessor')
    def test_step_size_defaults_to_min_extent_size(self, mock_processor_class):
        """Test that step_size defaults to min_extent_size when not specified."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        with patch('sys.argv', [
            'image_reconstructor_generator.py',
            str(self.image_file)
        ]):
            with patch('sys.stdin', StringIO("")):
                with patch('sys.stderr', StringIO()):
                    with patch('sys.stdout') as mock_stdout:
                        mock_stdout.isatty.return_value = False
                        main()

                    # Verify ImageProcessor was called with step_size matching min_extent_size
                    call_args = mock_processor_class.call_args
                    # Default min_extent_size is 1048576
                    self.assertEqual(call_args.kwargs['step_size'], 1048576)
                    self.assertEqual(call_args.kwargs['step_size'], call_args.kwargs['min_extent_size'])

    def test_step_size_must_be_multiple_of_block_size(self):
        """Test that step_size must be a multiple of block_size."""
        with patch('sys.argv', [
            'image_reconstructor_generator.py',
            str(self.image_file),
            '-b', '4096',
            '-s', '4097'  # Not a multiple of 4096
        ]):
            with patch('sys.stdin', StringIO("")):
                with patch('sys.stderr', StringIO()):
                    with self.assertRaises(SystemExit) as cm:
                        main()

                    self.assertEqual(cm.exception.code, 2)

    @patch('image_reconstructor_generator.ImageProcessor')
    def test_step_size_with_custom_min_extent_size(self, mock_processor_class):
        """Test step_size used with custom min_extent_size."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        with patch('sys.argv', [
            'image_reconstructor_generator.py',
            str(self.image_file),
            '-m', '524288',
            '-s', '262144'
        ]):
            with patch('sys.stdin', StringIO("")):
                with patch('sys.stderr', StringIO()):
                    with patch('sys.stdout') as mock_stdout:
                        mock_stdout.isatty.return_value = False
                        main()

                    # Verify both parameters are passed correctly
                    call_args = mock_processor_class.call_args
                    self.assertEqual(call_args.kwargs['min_extent_size'], 524288)
                    self.assertEqual(call_args.kwargs['step_size'], 262144)

    @patch('image_reconstructor_generator.ImageProcessor')
    def test_step_size_with_custom_block_size(self, mock_processor_class):
        """Test step_size used with custom block_size."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        with patch('sys.argv', [
            'image_reconstructor_generator.py',
            str(self.image_file),
            '-b', '2048',
            '-s', '8192'
        ]):
            with patch('sys.stdin', StringIO("")):
                with patch('sys.stderr', StringIO()):
                    with patch('sys.stdout') as mock_stdout:
                        mock_stdout.isatty.return_value = False
                        main()

                    # Verify both parameters are passed correctly
                    call_args = mock_processor_class.call_args
                    self.assertEqual(call_args.kwargs['block_size'], 2048)
                    self.assertEqual(call_args.kwargs['step_size'], 8192)


class TestStepSizeEffect(unittest.TestCase):
    """Tests for the effect of step size on extent discovery."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_file = Path(self.temp_dir.name) / "image.img"
        self.file1 = Path(self.temp_dir.name) / "file1.txt"

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_step_size_stored_correctly(self):
        """Test that step_size is stored in processor."""
        self.image_file.write_bytes(b"A" * 100000)

        processor = ImageProcessor(
            self.image_file,
            step_size=131072
        )

        self.assertEqual(processor.step_size, 131072)
        self.assertTrue(hasattr(processor, 'step_blocks'))

    def test_step_blocks_calculation(self):
        """Test that step_blocks is correctly calculated from step_size."""
        self.image_file.write_bytes(b"A" * 100000)

        block_size = 4096
        step_size = 16384  # Exactly 4 blocks

        processor = ImageProcessor(
            self.image_file,
            block_size=block_size,
            step_size=step_size
        )

        self.assertEqual(processor.step_blocks, 4)
        self.assertEqual(processor.step_blocks * processor.block_size, step_size)

    def test_coarse_step_size_skips_more(self):
        """Test that coarser step size (larger value) represents more blocks."""
        self.image_file.write_bytes(b"A" * 100000)

        processor_coarse = ImageProcessor(
            self.image_file,
            block_size=4096,
            step_size=1048576  # 256 blocks
        )

        processor_fine = ImageProcessor(
            self.image_file,
            block_size=4096,
            step_size=262144  # 64 blocks
        )

        # Coarser step skips more blocks
        self.assertGreater(processor_coarse.step_blocks, processor_fine.step_blocks)
        self.assertEqual(processor_coarse.step_blocks, 256)
        self.assertEqual(processor_fine.step_blocks, 64)

    def test_very_small_step_size(self):
        """Test with very small step size (one block)."""
        self.image_file.write_bytes(b"A" * 100000)

        processor = ImageProcessor(
            self.image_file,
            block_size=4096,
            step_size=4096  # Exactly one block
        )

        self.assertEqual(processor.step_blocks, 1)

    def test_very_large_step_size(self):
        """Test with very large step size."""
        self.image_file.write_bytes(b"A" * 100000)

        processor = ImageProcessor(
            self.image_file,
            block_size=4096,
            step_size=10485760  # 10 MiB
        )

        self.assertEqual(processor.step_blocks, 2560)


if __name__ == '__main__':
    unittest.main()
