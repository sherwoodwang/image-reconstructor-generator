"""Tests for the generate_shell_wrapper function."""

import unittest
import tempfile
import subprocess
import re
from pathlib import Path
from io import BytesIO
from typing import cast, Match

from image_reconstructor_generator import generate_shell_wrapper


class TestShellWrapper(unittest.TestCase):
    """Test cases for generate_shell_wrapper function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_basic_wrapper_structure(self):
        """Test that the wrapper generates correct structure."""
        # Create a test attachment
        attachment_data = b'Hello, World!'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        # Simple script
        script_text = "#!/bin/sh\necho 'test'\n"

        # Generate wrapper
        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [(0, 5)], attachment_file, f)

        # Read and verify structure
        with open(output_file, 'rb') as f:
            content = f.read()

        # Check for shebang
        self.assertTrue(content.startswith(b'#!/bin/sh\n'))

        # Check for offset variable
        self.assertIn(b'data_offset=', content)

        # Check for embedded script
        self.assertIn(b"echo 'test'", content)

    def test_offset_calculation(self):
        """Test that offsets are calculated correctly."""
        attachment_data = b'0123456789'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        script_text = "#!/bin/sh\necho test\n"

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [(0, 10)], attachment_file, f)

        # Read the file
        with open(output_file, 'rb') as f:
            content = f.read()

        # Extract offset value
        header = content[:500].decode('utf-8', errors='ignore')
        data_offset_match = re.search(r'data_offset=(\d+)', header)
        self.assertIsNotNone(data_offset_match)
        data_offset = int(cast(Match[str], data_offset_match).group(1))

        # Verify data_offset points to attachment data
        # The attachment data should be exactly what we specified
        attachment_data_extracted = content[data_offset:data_offset + 10]
        self.assertEqual(attachment_data_extracted, attachment_data)

    def test_attachment_data_inclusion(self):
        """Test that attachment data is correctly included."""
        attachment_data = b'ABCDEFGHIJKLMNOP'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        script_text = "#!/bin/sh\n"

        # Include ranges [0:5] and [10:15]
        attachment_ranges = [(0, 5), (10, 15)]

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, attachment_ranges, attachment_file, f)

        # Read and verify
        with open(output_file, 'rb') as f:
            content = f.read()

        # Find data_offset
        header = content[:500].decode('utf-8', errors='ignore')
        match = re.search(r'data_offset=(\d+)', header)
        self.assertIsNotNone(match)
        data_offset = int(cast(Match[str], match).group(1))

        # Extract embedded data
        embedded_data = content[data_offset:]

        # Should be concatenation of the ranges
        expected = b'ABCDEKLMNO'
        self.assertEqual(embedded_data, expected)

    def test_empty_attachment_ranges(self):
        """Test with no attachment ranges (all data from input files)."""
        attachment_data = b'test'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        script_text = "#!/bin/sh\ndd if=file.bin bs=1 count=10\n"

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [], attachment_file, f)

        # Should succeed without error
        with open(output_file, 'rb') as f:
            content = f.read()

        # Find data_offset
        header = content[:500].decode('utf-8', errors='ignore')
        data_offset_match = re.search(r'data_offset=(\d+)', header)
        self.assertIsNotNone(data_offset_match)
        data_offset = int(cast(Match[str], data_offset_match).group(1))

        # No embedded data after data_offset
        self.assertEqual(len(content), data_offset)

    def test_script_execution(self):
        """Test that the generated wrapper can execute successfully."""
        # Create test attachment
        attachment_data = b'Hello, World!'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        # Script that outputs the embedded data
        script_text = """#!/bin/sh
dd if="$script_file" bs=1 skip=$((data_offset + 0)) count=5 2>/dev/null
"""

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [(0, 5)], attachment_file, f)

        # Make executable and run
        output_file.chmod(0o755)
        result = subprocess.run(['sh', str(output_file)], capture_output=True)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'Hello')

    def test_large_script(self):
        """Test with a larger script embedded directly."""
        attachment_data = b'test data'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        # Generate a large script with many lines
        script_lines = ['#!/bin/sh']
        for i in range(100):
            script_lines.append(f'# Comment line {i}')
        script_text = '\n'.join(script_lines) + '\n'

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [(0, 9)], attachment_file, f)

        # Verify file was created
        self.assertTrue(output_file.exists())

        # Read the wrapper
        with open(output_file, 'rb') as f:
            content = f.read()

        # The script should be embedded in the wrapper
        # Check that the script content is present
        self.assertIn(b'# Comment line 50', content)

    def test_multiple_attachment_ranges(self):
        """Test with multiple non-contiguous attachment ranges."""
        attachment_data = b'0123456789ABCDEFGHIJ'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        script_text = "#!/bin/sh\necho test\n"

        # Multiple ranges: [0:5], [10:15], [18:20]
        attachment_ranges = [(0, 5), (10, 15), (18, 20)]

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, attachment_ranges, attachment_file, f)

        # Verify embedded data
        with open(output_file, 'rb') as f:
            content = f.read()

        header = content[:500].decode('utf-8', errors='ignore')
        data_offset_match = re.search(r'data_offset=(\d+)', header)
        self.assertIsNotNone(data_offset_match)
        data_offset = int(cast(Match[str], data_offset_match).group(1))

        embedded = content[data_offset:]
        expected = b'01234' + b'ABCDE' + b'IJ'
        self.assertEqual(embedded, expected)

    def test_binary_output_stream(self):
        """Test with a binary output stream."""
        attachment_data = b'binary test'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        script_text = "#!/bin/sh\n"

        # Use BytesIO as output
        output = BytesIO()
        generate_shell_wrapper(script_text, [(0, 11)], attachment_file, output)

        # Verify data was written
        output.seek(0)
        content = output.read()

        self.assertTrue(content.startswith(b'#!/bin/sh\n'))
        self.assertIn(b'data_offset=', content)

    def test_special_characters_in_script(self):
        """Test script with special shell characters."""
        attachment_data = b'test'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        # Script with various special characters
        script_text = """#!/bin/sh
echo "test 'quotes' and $vars"
echo 'single $quotes'
"""

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [], attachment_file, f)

        # Verify it was embedded correctly
        with open(output_file, 'rb') as f:
            content = f.read()

        # The script should be embedded directly in the wrapper
        self.assertIn(b"echo \"test 'quotes' and $vars\"", content)
        self.assertIn(b"echo 'single $quotes'", content)

    def test_multibyte_characters_in_script(self):
        """Test script with multi-byte UTF-8 characters."""
        attachment_data = b'test data'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        # Script with various multi-byte characters
        # Chinese, Japanese, emoji, and other UTF-8 characters
        script_text = """#!/bin/sh
# 中文注释 (Chinese comment)
# 日本語コメント (Japanese comment)
# Emoji: 🚀 🎉 ✨
echo "Testing multi-byte: café, naïve, 中文"
"""

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [(0, 5)], attachment_file, f)

        # Read and verify structure
        with open(output_file, 'rb') as f:
            content = f.read()

        # Extract offset
        data_offset_match = re.search(rb'data_offset=(\d+)', content)
        self.assertIsNotNone(data_offset_match)
        data_offset = int(cast(Match[bytes], data_offset_match).group(1))

        # Verify the script is embedded correctly (check for multi-byte characters)
        self.assertIn('中文注释'.encode('utf-8'), content)
        self.assertIn('🚀'.encode('utf-8'), content)

        # Verify attachment data is at the correct offset
        attachment_data_extracted = content[data_offset:data_offset + 5]
        self.assertEqual(attachment_data_extracted, b'test ')

    def test_multibyte_characters_offset_accuracy(self):
        """Test that offsets are byte-accurate with multi-byte characters."""
        attachment_data = b'0123456789'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        # Create a script with multi-byte characters
        script_text = "#!/bin/sh\n# Comment: 你好世界 🌍\necho test\n"

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [(0, 10)], attachment_file, f)

        with open(output_file, 'rb') as f:
            content = f.read()

        # Parse offset from header
        data_offset_match = re.search(rb'data_offset=(\d+)', content)
        self.assertIsNotNone(data_offset_match)
        data_offset = int(cast(Match[bytes], data_offset_match).group(1))

        # Verify that the embedded script contains the multi-byte characters
        self.assertIn('你好世界'.encode('utf-8'), content)
        self.assertIn('🌍'.encode('utf-8'), content)

        # Verify attachment data starts exactly at data_offset
        self.assertEqual(content[data_offset:], attachment_data)

    def test_emoji_in_script_comments(self):
        """Test script with emoji characters in comments."""
        attachment_data = b'emoji test'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        # Script with various emoji
        script_text = """#!/bin/sh
# Status: ✅ ❌ ⚠️
# Progress: 📊 📈 📉
# Files: 📁 📄 📝
echo "Script with emoji comments"
"""

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [(0, 10)], attachment_file, f)

        # Verify the script executes successfully
        output_file.chmod(0o755)
        result = subprocess.run(['sh', str(output_file)], capture_output=True)

        # Should execute without errors
        self.assertEqual(result.returncode, 0)

    def test_various_unicode_ranges(self):
        """Test script with characters from various Unicode ranges."""
        attachment_data = b'unicode'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        # Script with diverse Unicode characters
        script_text = """#!/bin/sh
# Latin Extended: àáâãäåæçèéêë
# Cyrillic: АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ
# Arabic: العربية
# Hebrew: עברית
# Greek: Ελληνικά
# Thai: ไทย
# Korean: 한국어
echo "Diverse Unicode test"
"""

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [], attachment_file, f)

        # Verify the script is embedded correctly
        with open(output_file, 'rb') as f:
            content = f.read()

        # Check that various Unicode characters are present
        self.assertIn('àáâãäåæçèéêë'.encode('utf-8'), content)
        self.assertIn('АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'.encode('utf-8'), content)
        self.assertIn('العربية'.encode('utf-8'), content)
        self.assertIn('한국어'.encode('utf-8'), content)

    def test_placeholder_only_replaced_once(self):
        """Test that placeholder is only replaced in the header, not in the embedded script."""
        attachment_data = b'test data'
        attachment_file = self.temp_path / 'test.img'
        attachment_file.write_bytes(attachment_data)

        # Create a script that contains the placeholder pattern
        # This should NOT be replaced - only the header placeholder should be replaced
        script_text = """#!/bin/sh
# This script has a comment with data_offset=0000000000 in it
echo "data_offset=0000000000"
"""

        output_file = self.temp_path / 'wrapper.sh'
        with open(output_file, 'w') as f:
            generate_shell_wrapper(script_text, [(0, 9)], attachment_file, f)

        # Read the generated wrapper
        with open(output_file, 'rb') as f:
            content = f.read()

        # Parse the data_offset from the header (first occurrence)
        data_offset_match = re.search(rb'data_offset=(\d+)', content)
        self.assertIsNotNone(data_offset_match)
        data_offset = int(cast(Match[bytes], data_offset_match).group(1))

        # The header's data_offset should be replaced with the actual offset
        self.assertNotEqual(data_offset, 0)

        # The embedded script should still contain the original placeholder
        # Count occurrences of the pattern
        pattern = b'data_offset=0000000000'
        count = content.count(pattern)

        # Should find exactly 2 occurrences:
        # 1. In the comment
        # 2. In the echo statement
        # The header placeholder should have been replaced
        self.assertEqual(count, 2)

        # Verify the script still has the placeholder in the embedded part
        self.assertIn(b'# This script has a comment with data_offset=0000000000 in it', content)
        self.assertIn(b'echo "data_offset=0000000000"', content)


if __name__ == '__main__':
    unittest.main()
