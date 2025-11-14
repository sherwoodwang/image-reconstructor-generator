#!/usr/bin/env python3
"""
Tests for the image_rebuilder module.
"""

import unittest
import tempfile
import sys
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_rebuilder import ImageProcessor, read_file_list, main


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

        # Should not raise an error
        processor.process_file("test.txt")

    def test_finalize_callable(self):
        """Test that finalize() method is callable."""
        processor = ImageProcessor(self.image_file, self.output)

        # Should not raise an error
        processor.finalize()


class TestMainFunction(unittest.TestCase):
    """Tests for the main() function and argument parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_file = Path(self.temp_dir.name) / "test.img"
        self.image_file.touch()

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    @patch('image_rebuilder.ImageProcessor')
    def test_main_with_stdin(self, mock_processor_class):
        """Test main() with stdin input."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        test_input = "file1.txt\nfile2.txt\n"

        with patch('sys.argv', ['image_rebuilder.py', str(self.image_file)]):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('sys.stderr', StringIO()):
                    main()

        # Verify processor methods were called
        mock_processor.begin.assert_called_once()
        self.assertEqual(mock_processor.process_file.call_count, 2)
        mock_processor.finalize.assert_called_once()

    @patch('image_rebuilder.ImageProcessor')
    def test_main_with_input_file(self, mock_processor_class):
        """Test main() with input file."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        # Create input file
        input_file = Path(self.temp_dir.name) / "files.txt"
        input_file.write_text("file1.txt\nfile2.txt\nfile3.txt\n")

        with patch('sys.argv', ['image_rebuilder.py', str(self.image_file), '-i', str(input_file)]):
            with patch('sys.stderr', StringIO()):
                main()

        # Verify processor methods were called
        mock_processor.begin.assert_called_once()
        self.assertEqual(mock_processor.process_file.call_count, 3)
        mock_processor.finalize.assert_called_once()

    @patch('image_rebuilder.ImageProcessor')
    def test_main_with_null_separated(self, mock_processor_class):
        """Test main() with null-separated input."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        test_input = "file1.txt\0file2.txt\0"

        with patch('sys.argv', ['image_rebuilder.py', '-0', str(self.image_file)]):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('sys.stderr', StringIO()):
                    main()

        # Verify processor methods were called
        mock_processor.begin.assert_called_once()
        self.assertEqual(mock_processor.process_file.call_count, 2)
        mock_processor.finalize.assert_called_once()

    @patch('image_rebuilder.ImageProcessor')
    def test_main_with_output_file(self, mock_processor_class):
        """Test main() with output file."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        output_file = Path(self.temp_dir.name) / "output.sh"
        test_input = "file1.txt\n"

        with patch('sys.argv', ['image_rebuilder.py', str(self.image_file), '-o', str(output_file)]):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('sys.stderr', StringIO()):
                    main()

        # Verify output file was created
        self.assertTrue(output_file.exists())

    def test_main_nonexistent_image(self):
        """Test main() with nonexistent image file."""
        nonexistent = Path(self.temp_dir.name) / "nonexistent.img"

        with patch('sys.argv', ['image_rebuilder.py', str(nonexistent)]):
            with patch('sys.stderr', StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    main()

                self.assertEqual(cm.exception.code, 2)

    def test_main_image_is_directory(self):
        """Test main() when image path is a directory."""
        dir_path = Path(self.temp_dir.name) / "testdir"
        dir_path.mkdir()

        with patch('sys.argv', ['image_rebuilder.py', str(dir_path)]):
            with patch('sys.stderr', StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    main()

                self.assertEqual(cm.exception.code, 2)

    @patch('image_rebuilder.ImageProcessor')
    def test_main_counts_files(self, mock_processor_class):
        """Test that main() prints correct file count."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        test_input = "file1.txt\nfile2.txt\nfile3.txt\n"

        with patch('sys.argv', ['image_rebuilder.py', str(self.image_file)]):
            with patch('sys.stdin', StringIO(test_input)):
                stderr_capture = StringIO()
                with patch('sys.stderr', stderr_capture):
                    main()

        stderr_output = stderr_capture.getvalue()
        self.assertIn("Processed 3 files", stderr_output)

    @patch('image_rebuilder.ImageProcessor')
    def test_main_empty_input(self, mock_processor_class):
        """Test main() with empty input."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        test_input = ""

        with patch('sys.argv', ['image_rebuilder.py', str(self.image_file)]):
            with patch('sys.stdin', StringIO(test_input)):
                stderr_capture = StringIO()
                with patch('sys.stderr', stderr_capture):
                    main()

        # Verify processor methods were called
        mock_processor.begin.assert_called_once()
        self.assertEqual(mock_processor.process_file.call_count, 0)
        mock_processor.finalize.assert_called_once()

        stderr_output = stderr_capture.getvalue()
        self.assertIn("Processed 0 files", stderr_output)


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
        input_file = Path(self.temp_dir.name) / "files.txt"
        input_file.write_text("file1.txt\nfile2.txt\nfile3.txt\n")

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
        input_file = Path(self.temp_dir.name) / "files.txt"
        input_file.write_text("file1.txt\0file with spaces.txt\0file3.txt\0")

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
