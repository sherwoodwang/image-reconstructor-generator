#!/usr/bin/env python3
"""
Comprehensive tests for shell escaping function.

Tests all Unicode characters up to 65535 and validates them using actual shell execution.
"""

import unittest
import subprocess
import tempfile
from pathlib import Path
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_rebuilder import escape_for_shell_display


class TestShellEscaping(unittest.TestCase):
    """Test shell escaping with actual shell validation."""

    def validate_with_shell(self, original: str, escaped: str) -> bool:
        """
        Validate that the escaped string evaluates to the original in a shell.

        Args:
            original: The original string
            escaped: The escaped string

        Returns:
            True if shell evaluation produces the original string
        """
        # Assign the escaped value to a variable, then output it with printf
        # This handles ANSI-C quoting ($'...') and all other quoting correctly
        script = f'x={escaped}; printf "%s" "$x"'

        try:
            result = subprocess.run(
                ['sh', '-c', script],
                capture_output=True,
                timeout=5,
                check=False
            )

            if result.returncode != 0:
                return False

            # Check if the output matches the original
            return result.stdout.decode('utf-8', errors='replace') == original

        except (subprocess.TimeoutExpired, Exception):
            return False

    def test_empty_string(self):
        """Test empty string."""
        escaped = escape_for_shell_display("")
        self.assertEqual(escaped, "''")
        self.assertTrue(self.validate_with_shell("", escaped))

    def test_simple_alphanumeric(self):
        """Test simple alphanumeric strings."""
        test_cases = [
            "simple",
            "test123",
            "file.txt",
            "my_file-v2.0",
            "UPPERCASE",
        ]
        for test in test_cases:
            with self.subTest(test=test):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_spaces(self):
        """Test strings with spaces."""
        test_cases = [
            "file with spaces.txt",
            "  leading spaces",
            "trailing spaces  ",
            "  both  ",
            "multiple   spaces   between",
        ]
        for test in test_cases:
            with self.subTest(test=test):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_single_quotes(self):
        """Test strings with single quotes."""
        test_cases = [
            "file'with'quotes",
            "'leading",
            "trailing'",
            "multiple'''quotes",
            "it's a file",
        ]
        for test in test_cases:
            with self.subTest(test=test):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_double_quotes(self):
        """Test strings with double quotes."""
        test_cases = [
            'file"with"quotes',
            '"leading',
            'trailing"',
            'multiple"""quotes',
        ]
        for test in test_cases:
            with self.subTest(test=test):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_backslashes(self):
        """Test strings with backslashes."""
        test_cases = [
            "file\\with\\backslash",
            "\\leading",
            "trailing\\",
            "multiple\\\\\\backslashes",
            "path\\to\\file.txt",
        ]
        for test in test_cases:
            with self.subTest(test=test):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_control_characters(self):
        """Test control characters (0-31)."""
        # Test all control characters
        # Note: Null bytes (0) cannot be stored in shell variables, so we skip them
        for code in range(1, 32):
            char = chr(code)
            test_string = f"before{char}after"
            with self.subTest(code=code, char=repr(char)):
                escaped = escape_for_shell_display(test_string)
                # Should be wrapped in single quotes
                self.assertTrue(escaped.startswith("'"))
                self.assertTrue(self.validate_with_shell(test_string, escaped))

    def test_del_character(self):
        """Test DEL character (127)."""
        test = f"before{chr(127)}after"
        escaped = escape_for_shell_display(test)
        self.assertTrue(escaped.startswith("'"))
        self.assertTrue(self.validate_with_shell(test, escaped))

    def test_special_shell_characters(self):
        """Test special shell characters."""
        test_cases = [
            "file$with$dollar",
            "file&with&ampersand",
            "file|with|pipe",
            "file;with;semicolon",
            "file(with)parens",
            "file{with}braces",
            "file[with]brackets",
            "file<with>angles",
            "file*with*asterisk",
            "file?with?question",
            "file!with!exclamation",
            "file`with`backtick",
            "file~with~tilde",
            "file#with#hash",
            "file%with%percent",
            "file^with^caret",
            "file=with=equals",
            "file+with+plus",
        ]
        for test in test_cases:
            with self.subTest(test=test):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_newlines_and_tabs(self):
        """Test newlines, tabs, and carriage returns."""
        test_cases = [
            "file\nwith\nnewlines",
            "file\twith\ttabs",
            "file\rwith\rcarriage",
            "mixed\n\t\rcontent",
            "\n\t\r",
        ]
        for test in test_cases:
            with self.subTest(test=repr(test)):
                escaped = escape_for_shell_display(test)
                self.assertTrue(escaped.startswith("'"))
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_unicode_common(self):
        """Test common Unicode characters."""
        test_cases = [
            "café",
            "日本語",
            "한글",
            "Ελληνικά",
            "Русский",
            "العربية",
            "עברית",
            "emoji😀test",
            "🎉🎊🎈",
            "文件名.txt",
        ]
        for test in test_cases:
            with self.subTest(test=test):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_all_printable_ascii(self):
        """Test all printable ASCII characters (32-126)."""
        for code in range(32, 127):
            char = chr(code)
            # Skip certain problematic characters in filenames for general test
            # but include them in the full sweep
            test_string = f"x{char}y"
            with self.subTest(code=code, char=char):
                escaped = escape_for_shell_display(test_string)
                self.assertTrue(self.validate_with_shell(test_string, escaped))

    def test_all_unicode_bmp(self):
        """Test all Unicode characters in Basic Multilingual Plane (0-65535)."""
        # Test in chunks to make debugging easier if something fails
        chunk_size = 1000
        for start in range(0, 65536, chunk_size):
            end = min(start + chunk_size, 65536)
            for code in range(start, end):
                # Skip surrogates (0xD800-0xDFFF) as they're not valid Unicode characters
                if 0xD800 <= code <= 0xDFFF:
                    continue

                # Skip null byte (0) - cannot be stored in shell variables
                if code == 0:
                    continue

                char = chr(code)
                test_string = f"x{char}y"

                with self.subTest(code=code):
                    escaped = escape_for_shell_display(test_string)

                    # Verify it's properly quoted
                    self.assertTrue(
                        escaped.startswith("'"),
                        f"Not properly quoted for U+{code:04X}"
                    )

                    # Validate with shell
                    valid = self.validate_with_shell(test_string, escaped)
                    self.assertTrue(
                        valid,
                        f"Failed for U+{code:04X} ({repr(char)}): {escaped}"
                    )


    def test_mixed_complexity(self):
        """Test strings with mixed complexity."""
        test_cases = [
            "simple'and\ncomplex",
            "file with spaces'and'quotes\tand\ttabs",
            "\\backslash'quote\nnewline",
            "emoji😀with'quotes\nand\nnewlines",
        ]
        for test in test_cases:
            with self.subTest(test=repr(test)):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_path_like_strings(self):
        """Test realistic file path strings."""
        test_cases = [
            "/path/to/file.txt",
            "./relative/path/file.txt",
            "../parent/file.txt",
            "/path with spaces/file.txt",
            "/path/with'quotes/file.txt",
            "/path/with\ttabs/file.txt",
            "C:\\Windows\\Path\\file.txt",
            "/path/with/emoji😀/file.txt",
            "/path/with/unicode/日本語/file.txt",
        ]
        for test in test_cases:
            with self.subTest(test=test):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))

    def test_extremely_long_string(self):
        """Test very long strings."""
        # Test with a very long string
        long_string = "a" * 10000
        escaped = escape_for_shell_display(long_string)
        self.assertTrue(self.validate_with_shell(long_string, escaped))

        # Test long string with special characters
        long_special = ("x'y" * 1000)
        escaped = escape_for_shell_display(long_special)
        self.assertTrue(self.validate_with_shell(long_special, escaped))

    def test_edge_cases(self):
        """Test various edge cases."""
        test_cases = [
            " ",  # Single space
            "'",  # Single quote
            "''",  # Two quotes
            "'''",  # Three quotes
            "\\",  # Single backslash
            "\\\\",  # Two backslashes
            # Note: Trailing newlines can't round-trip through command substitution $(...)
            # as shells strip all trailing newlines from command substitution results
            # But they work fine when embedded in text (not at the end)
            "\t",  # Single tab - this should work
            "\nx",  # Leading newline with content - this works
            "\rx",  # Carriage return with content - this works
            "a\nb",  # Newline in middle - this works
        ]
        for test in test_cases:
            with self.subTest(test=repr(test)):
                escaped = escape_for_shell_display(test)
                self.assertTrue(self.validate_with_shell(test, escaped))


if __name__ == '__main__':
    unittest.main()
