#!/usr/bin/env python3
"""
Tests for the read_file_list function.
"""

import unittest
import sys
from pathlib import Path
from io import StringIO

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_reconstructor_generator import read_file_list


class TestReadFileList(unittest.TestCase):
    """Tests for the read_file_list function."""

    def test_newline_separated_basic(self):
        """Test reading newline-separated file list."""
        input_data = "file1.txt\nfile2.txt\nfile3.txt\n"
        stream = StringIO(input_data)

        result = list(read_file_list(stream, null_separated=False))

        self.assertEqual(result, ["file1.txt", "file2.txt", "file3.txt"])

    def test_newline_separated_with_empty_lines(self):
        """Test that empty lines are skipped."""
        input_data = "file1.txt\n\nfile2.txt\n\n\nfile3.txt\n"
        stream = StringIO(input_data)

        result = list(read_file_list(stream, null_separated=False))

        self.assertEqual(result, ["file1.txt", "file2.txt", "file3.txt"])

    def test_newline_separated_with_spaces(self):
        """Test files with spaces in names."""
        input_data = "file 1.txt\nfile 2.txt\n"
        stream = StringIO(input_data)

        result = list(read_file_list(stream, null_separated=False))

        self.assertEqual(result, ["file 1.txt", "file 2.txt"])

    def test_newline_separated_crlf(self):
        """Test handling of CRLF line endings."""
        input_data = "file1.txt\r\nfile2.txt\r\n"
        stream = StringIO(input_data)

        result = list(read_file_list(stream, null_separated=False))

        self.assertEqual(result, ["file1.txt", "file2.txt"])

    def test_null_separated_basic(self):
        """Test reading null-separated file list."""
        input_data = "file1.txt\0file2.txt\0file3.txt\0"
        stream = StringIO(input_data)

        result = list(read_file_list(stream, null_separated=True))

        self.assertEqual(result, ["file1.txt", "file2.txt", "file3.txt"])

    def test_null_separated_with_special_chars(self):
        """Test null-separated list with special characters."""
        input_data = "file\nwith\nnewlines.txt\0file with spaces.txt\0"
        stream = StringIO(input_data)

        result = list(read_file_list(stream, null_separated=True))

        self.assertEqual(result, ["file\nwith\nnewlines.txt", "file with spaces.txt"])

    def test_null_separated_no_trailing_null(self):
        """Test null-separated list without trailing null."""
        input_data = "file1.txt\0file2.txt"
        stream = StringIO(input_data)

        result = list(read_file_list(stream, null_separated=True))

        self.assertEqual(result, ["file1.txt", "file2.txt"])

    def test_empty_input(self):
        """Test handling of empty input."""
        stream = StringIO("")

        result = list(read_file_list(stream, null_separated=False))

        self.assertEqual(result, [])

    def test_empty_input_null_separated(self):
        """Test handling of empty input for null-separated."""
        stream = StringIO("")

        result = list(read_file_list(stream, null_separated=True))

        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
