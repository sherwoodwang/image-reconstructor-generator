#!/usr/bin/env python3
"""
Integration tests for the full workflow.
"""

import unittest
import tempfile
import sys
from pathlib import Path
from io import StringIO
from unittest.mock import patch

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_rebuilder import main


class TestIntegration(unittest.TestCase):
    """Integration tests for the full workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_file = Path(self.temp_dir.name) / "test.img"
        self.image_file.write_bytes(b"test image content")

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_end_to_end_newline_separated(self):
        """Test complete workflow with newline-separated input."""
        # Create the files that will be processed
        file1 = Path(self.temp_dir.name) / "file1.txt"
        file2 = Path(self.temp_dir.name) / "file2.txt"
        file3 = Path(self.temp_dir.name) / "file3.txt"
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")
        file3.write_bytes(b"content3")

        input_file = Path(self.temp_dir.name) / "files.txt"
        input_file.write_text(f"{file1}\n{file2}\n{file3}\n")

        output_file = Path(self.temp_dir.name) / "output.sh"

        with patch('sys.argv', [
            'image_rebuilder.py',
            str(self.image_file),
            '-i', str(input_file),
            '-o', str(output_file)
        ]):
            with patch('sys.stderr', StringIO()):
                main()

        # Verify output file was created
        self.assertTrue(output_file.exists())

    def test_end_to_end_null_separated(self):
        """Test complete workflow with null-separated input."""
        # Create the files that will be processed
        file1 = Path(self.temp_dir.name) / "file1.txt"
        file2 = Path(self.temp_dir.name) / "file with spaces.txt"
        file3 = Path(self.temp_dir.name) / "file3.txt"
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")
        file3.write_bytes(b"content3")

        input_file = Path(self.temp_dir.name) / "files.txt"
        input_file.write_text(f"{file1}\0{file2}\0{file3}\0")

        output_file = Path(self.temp_dir.name) / "output.sh"

        with patch('sys.argv', [
            'image_rebuilder.py',
            str(self.image_file),
            '-i', str(input_file),
            '-o', str(output_file),
            '-0'
        ]):
            with patch('sys.stderr', StringIO()):
                main()

        # Verify output file was created
        self.assertTrue(output_file.exists())


if __name__ == '__main__':
    unittest.main()
