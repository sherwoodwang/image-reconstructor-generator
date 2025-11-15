#!/usr/bin/env python3
"""
Integration tests for the full workflow.
"""

import unittest
import tempfile
import sys
import os
from pathlib import Path
from io import StringIO
from unittest.mock import patch

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_reconstructor_generator import main


class TestIntegration(unittest.TestCase):
    """Integration tests for the full workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_dir_path = Path(self.temp_dir)
        self.image_file = self.temp_dir_path / "test.img"
        self.image_file.write_bytes(b"test image content")
        self.original_cwd = Path.cwd()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_end_to_end_newline_separated(self):
        """Test complete workflow with newline-separated input."""
        # Create the files that will be processed
        file1 = self.temp_dir_path / "file1.txt"
        file2 = self.temp_dir_path / "file2.txt"
        file3 = self.temp_dir_path / "file3.txt"
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")
        file3.write_bytes(b"content3")

        input_file = self.temp_dir_path / "files.txt"
        input_file.write_text(f"{file1}\n{file2}\n{file3}\n")

        output_file = self.temp_dir_path / "output.sh"

        # Change to temp directory so files are within working directory
        os.chdir(self.temp_dir)
        try:
            with patch('sys.argv', [
                'image_reconstructor_generator.py',
                str(self.image_file.relative_to(self.temp_dir_path)),
                '-i', str(input_file.relative_to(self.temp_dir_path)),
                '-o', str(output_file.relative_to(self.temp_dir_path))
            ]):
                with patch('sys.stderr', StringIO()):
                    main()

            # Verify output file was created
            self.assertTrue(output_file.exists())
        finally:
            os.chdir(self.original_cwd)

    def test_end_to_end_null_separated(self):
        """Test complete workflow with null-separated input."""
        # Create the files that will be processed
        file1 = self.temp_dir_path / "file1.txt"
        file2 = self.temp_dir_path / "file with spaces.txt"
        file3 = self.temp_dir_path / "file3.txt"
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")
        file3.write_bytes(b"content3")

        input_file = self.temp_dir_path / "files.txt"
        input_file.write_text(f"{file1}\0{file2}\0{file3}\0")

        output_file = self.temp_dir_path / "output.sh"

        # Change to temp directory so files are within working directory
        os.chdir(self.temp_dir)
        try:
            with patch('sys.argv', [
                'image_reconstructor_generator.py',
                str(self.image_file.relative_to(self.temp_dir_path)),
                '-i', str(input_file.relative_to(self.temp_dir_path)),
                '-o', str(output_file.relative_to(self.temp_dir_path)),
                '-0'
            ]):
                with patch('sys.stderr', StringIO()):
                    main()

            # Verify output file was created
            self.assertTrue(output_file.exists())
        finally:
            os.chdir(self.original_cwd)


if __name__ == '__main__':
    unittest.main()
