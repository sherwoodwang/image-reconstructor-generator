"""Tests for the generate_reconstruction_sequence function."""

import unittest
from image_reconstructor_generator import generate_reconstruction_sequence


class TestReconstructionSequence(unittest.TestCase):
    """Test cases for generate_reconstruction_sequence function."""

    def test_empty_matches_returns_entire_image(self):
        """Test that empty matches returns the entire image as source."""
        matches = []
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        self.assertEqual(result, [('image', 0, 1000)])

    def test_single_match_at_start(self):
        """Test single match at the start of the image."""
        # Match: file bytes 0-100 -> image bytes 0-100
        matches = [('test_file.bin', 0, 100, 0, 100)]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        expected = [
            ('test_file.bin', 0, 100),
            ('image', 100, 1000)
        ]
        self.assertEqual(result, expected)

    def test_single_match_in_middle(self):
        """Test single match in the middle of the image."""
        # Match: file bytes 0-100 -> image bytes 300-400
        matches = [('test_file.bin', 0, 100, 300, 400)]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        expected = [
            ('image', 0, 300),
            ('test_file.bin', 0, 100),
            ('image', 400, 1000)
        ]
        self.assertEqual(result, expected)

    def test_single_match_at_end(self):
        """Test single match at the end of the image."""
        # Match: file bytes 0-100 -> image bytes 900-1000
        matches = [('test_file.bin', 0, 100, 900, 1000)]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        expected = [
            ('image', 0, 900),
            ('test_file.bin', 0, 100)
        ]
        self.assertEqual(result, expected)

    def test_multiple_non_overlapping_matches(self):
        """Test multiple non-overlapping matches."""
        # Match 1: file bytes 0-100 -> image bytes 100-200
        # Match 2: file bytes 200-300 -> image bytes 500-600
        matches = [
            ('file.bin', 0, 100, 100, 200),
            ('file.bin', 200, 300, 500, 600)
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        expected = [
            ('image', 0, 100),
            ('file.bin', 0, 100),
            ('image', 200, 500),
            ('file.bin', 200, 300),
            ('image', 600, 1000)
        ]
        self.assertEqual(result, expected)

    def test_overlapping_matches_keeps_first(self):
        """Test that overlapping matches are deduplicated, keeping the first one."""
        # Match 1: file bytes 0-200 -> image bytes 100-300 (comes first in image)
        # Match 2: file bytes 0-100 -> image bytes 150-250 (overlaps, should be skipped)
        matches = [
            ('file.bin', 0, 200, 100, 300),
            ('file.bin', 0, 100, 150, 250)
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        # Only the first match should be used since it comes first and covers the overlap
        expected = [
            ('image', 0, 100),
            ('file.bin', 0, 200),
            ('image', 300, 1000)
        ]
        self.assertEqual(result, expected)

    def test_partially_overlapping_matches_adjusted(self):
        """Test that partially overlapping matches are adjusted correctly."""
        # Match 1: file bytes 0-150 -> image bytes 100-250
        # Match 2: file bytes 0-200 -> image bytes 200-400 (partial overlap)
        # The second match overlaps from 200-250, so it should be adjusted to start at 250
        matches = [
            ('file.bin', 0, 150, 100, 250),
            ('file.bin', 0, 200, 200, 400)
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        # Second match should be adjusted: skip first 50 bytes (250-200=50)
        expected = [
            ('image', 0, 100),
            ('file.bin', 0, 150),      # First match
            ('file.bin', 50, 200),     # Second match, adjusted to start at byte 50
            ('image', 400, 1000)
        ]
        self.assertEqual(result, expected)

    def test_completely_covered_match_skipped(self):
        """Test that a match completely covered by another is skipped."""
        # Match 1: file bytes 0-300 -> image bytes 100-400 (larger match)
        # Match 2: file bytes 0-100 -> image bytes 150-250 (completely inside match 1)
        matches = [
            ('file.bin', 0, 300, 100, 400),
            ('file.bin', 0, 100, 150, 250)
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        # Only the first (larger) match should be used
        expected = [
            ('image', 0, 100),
            ('file.bin', 0, 300),
            ('image', 400, 1000)
        ]
        self.assertEqual(result, expected)

    def test_unsorted_matches_are_sorted(self):
        """Test that unsorted matches are properly sorted before processing."""
        # Provide matches in reverse order
        matches = [
            ('file.bin', 200, 300, 500, 600),  # Second in image order
            ('file.bin', 0, 100, 100, 200)     # First in image order
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        expected = [
            ('image', 0, 100),
            ('file.bin', 0, 100),
            ('image', 200, 500),
            ('file.bin', 200, 300),
            ('image', 600, 1000)
        ]
        self.assertEqual(result, expected)

    def test_prefers_longer_match_on_same_start(self):
        """Test that when multiple matches start at the same position, longer one is preferred."""
        # Both matches start at image byte 100
        # Match 1: file bytes 0-100 -> image bytes 100-200 (shorter)
        # Match 2: file bytes 0-300 -> image bytes 100-400 (longer)
        matches = [
            ('file.bin', 0, 100, 100, 200),
            ('file.bin', 0, 300, 100, 400)
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        # Should prefer the longer match (due to descending sort on end position)
        expected = [
            ('image', 0, 100),
            ('file.bin', 0, 300),
            ('image', 400, 1000)
        ]
        self.assertEqual(result, expected)

    def test_entire_image_covered_by_matches(self):
        """Test when the entire image is covered by matches."""
        # Match 1: file bytes 0-500 -> image bytes 0-500
        # Match 2: file bytes 500-1000 -> image bytes 500-1000
        matches = [
            ('file.bin', 0, 500, 0, 500),
            ('file.bin', 500, 1000, 500, 1000)
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        # No image data needed
        expected = [
            ('file.bin', 0, 500),
            ('file.bin', 500, 1000)
        ]
        self.assertEqual(result, expected)

    def test_adjacent_matches(self):
        """Test matches that are adjacent but not overlapping."""
        # Match 1: file bytes 0-100 -> image bytes 100-200
        # Match 2: file bytes 100-200 -> image bytes 200-300 (starts exactly where match 1 ends)
        matches = [
            ('file.bin', 0, 100, 100, 200),
            ('file.bin', 100, 200, 200, 300)
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        expected = [
            ('image', 0, 100),
            ('file.bin', 0, 100),
            ('file.bin', 100, 200),
            ('image', 300, 1000)
        ]
        self.assertEqual(result, expected)

    def test_zero_size_image(self):
        """Test with zero-size image."""
        matches = []
        image_size = 0

        result = generate_reconstruction_sequence(matches, image_size)

        # Should return image source with 0-0 range
        self.assertEqual(result, [('image', 0, 0)])

    def test_single_match_covering_entire_image(self):
        """Test single match that covers the entire image."""
        matches = [('test_file.bin', 0, 1000, 0, 1000)]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        # Only the file match, no image data needed
        expected = [('test_file.bin', 0, 1000)]
        self.assertEqual(result, expected)

    def test_multiple_overlapping_matches_complex(self):
        """Test complex scenario with multiple overlapping matches."""
        # Match 1: file bytes 0-100 -> image bytes 0-100
        # Match 2: file bytes 0-150 -> image bytes 50-200 (overlaps 50-100)
        # Match 3: file bytes 0-100 -> image bytes 180-280 (overlaps 180-200, extends 200-280)
        matches = [
            ('file.bin', 0, 100, 0, 100),
            ('file.bin', 0, 150, 50, 200),
            ('file.bin', 0, 100, 180, 280)
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        # Match 1: 0-100 (full)
        # Match 2: 50-200 (adjusted to 100-200, using bytes 50-150 from file)
        # Match 3: 180-280 (adjusted to 200-280, using bytes 20-100 from file)
        expected = [
            ('file.bin', 0, 100),      # Match 1
            ('file.bin', 50, 150),     # Match 2, adjusted
            ('file.bin', 20, 100),     # Match 3, adjusted
            ('image', 280, 1000)
        ]
        self.assertEqual(result, expected)

    def test_match_with_same_positions(self):
        """Test duplicate matches with identical positions."""
        # Two identical matches
        matches = [
            ('file.bin', 0, 100, 100, 200),
            ('file.bin', 0, 100, 100, 200)
        ]
        image_size = 1000

        result = generate_reconstruction_sequence(matches, image_size)

        # Should deduplicate and use only one
        expected = [
            ('image', 0, 100),
            ('file.bin', 0, 100),
            ('image', 200, 1000)
        ]
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
