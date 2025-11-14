#!/usr/bin/env python3
"""
Tests for the ImageProcessor class initialization and basic methods.
"""

import unittest
import tempfile
import sys
from pathlib import Path
from io import StringIO

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
        self.output = StringIO()

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

        # Should not raise an error
        processor.process_file(str(test_file))

    def test_finalize_callable(self):
        """Test that finalize() method is callable."""
        processor = ImageProcessor(self.image_file, self.output)

        # Should not raise an error
        processor.finalize()


if __name__ == '__main__':
    unittest.main()
