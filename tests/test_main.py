#!/usr/bin/env python3
"""
Tests for the main() function and command-line argument parsing.
"""

import unittest
import tempfile
import sys
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_rebuilder import main


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
                    with patch('sys.stdout') as mock_stdout:
                        mock_stdout.isatty.return_value = False
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
                with patch('sys.stdout') as mock_stdout:
                    mock_stdout.isatty.return_value = False
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
                    with patch('sys.stdout') as mock_stdout:
                        mock_stdout.isatty.return_value = False
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
        """Test that main() counts files correctly (file count is tracked in processor)."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        test_input = "file1.txt\nfile2.txt\nfile3.txt\n"

        with patch('sys.argv', ['image_rebuilder.py', str(self.image_file)]):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('sys.stdout') as mock_stdout:
                    mock_stdout.isatty.return_value = False
                    main()

        # Verify processor methods were called for each file
        mock_processor.begin.assert_called_once()
        self.assertEqual(mock_processor.process_file.call_count, 3)
        mock_processor.finalize.assert_called_once()

    @patch('image_rebuilder.ImageProcessor')
    def test_main_empty_input(self, mock_processor_class):
        """Test main() with empty input."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        test_input = ""

        with patch('sys.argv', ['image_rebuilder.py', str(self.image_file)]):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('sys.stdout') as mock_stdout:
                    mock_stdout.isatty.return_value = False
                    main()

        # Verify processor methods were called
        mock_processor.begin.assert_called_once()
        self.assertEqual(mock_processor.process_file.call_count, 0)
        mock_processor.finalize.assert_called_once()

    def test_block_size_argument_in_main(self):
        """Test that block size argument is properly passed from main()."""
        self.image_file.write_bytes(b"A" * 5000)

        with patch('sys.argv', [
            'image_rebuilder.py',
            str(self.image_file),
            '--block-size', '512'
        ]):
            with patch('sys.stdin', StringIO("")):
                with patch('sys.stderr', StringIO()):
                    # Capture the processor that was created
                    with patch('image_rebuilder.ImageProcessor') as mock_processor_class:
                        mock_processor = MagicMock()
                        mock_processor_class.return_value = mock_processor
                        with patch('sys.stdout') as mock_stdout:
                            mock_stdout.isatty.return_value = False
                            main()

                        # Verify ImageProcessor was called with block_size=512
                        call_args = mock_processor_class.call_args
                        self.assertEqual(call_args.kwargs['block_size'], 512)

    def test_block_size_short_argument(self):
        """Test that short form -b argument works for block size."""
        self.image_file.write_bytes(b"A" * 5000)

        with patch('sys.argv', [
            'image_rebuilder.py',
            str(self.image_file),
            '-b', '2048'
        ]):
            with patch('sys.stdin', StringIO("")):
                with patch('sys.stderr', StringIO()):
                    with patch('image_rebuilder.ImageProcessor') as mock_processor_class:
                        mock_processor = MagicMock()
                        mock_processor_class.return_value = mock_processor
                        with patch('sys.stdout') as mock_stdout:
                            mock_stdout.isatty.return_value = False
                            main()

                        # Verify ImageProcessor was called with block_size=2048
                        call_args = mock_processor_class.call_args
                        self.assertEqual(call_args.kwargs['block_size'], 2048)


if __name__ == '__main__':
    unittest.main()
