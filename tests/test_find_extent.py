#!/usr/bin/env python3
"""
Tests for the _find_extent_in_image method.
"""

import unittest
import tempfile
import sys
from pathlib import Path

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_rebuilder import ImageProcessor


class TestFindExtentInImage(unittest.TestCase):
    """Tests for the _find_extent_in_image method."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_file = Path(self.temp_dir.name) / "test.img"
        self.test_file = Path(self.temp_dir.name) / "test_file.txt"

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def _call_find_extent(self, processor, test_file, file_hashes, extent_blocks, file_start_block=0):
        """Helper to call _find_extent_in_image with file handles."""
        file_size = test_file.stat().st_size
        image_size = processor.image_file.stat().st_size
        with open(test_file, 'rb') as file_f, open(processor.image_file, 'rb') as image_f:
            return processor._find_extent_in_image(
                file_f, image_f, file_size, image_size,
                file_hashes, extent_blocks, file_start_block
            )

    def test_exact_match_at_start(self):
        """Test finding an extent that matches at the start of the image."""
        # Create image with known content
        block_size = 1024
        content = b"A" * block_size + b"B" * block_size + b"C" * block_size
        self.image_file.write_bytes(content)

        # Create file with matching content at start
        self.test_file.write_bytes(b"A" * block_size + b"B" * block_size)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Search for 1 block extent (should match at position 0 and extend to cover entire file)
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        # Should return (file_start=0, file_end=2, image_start=0, image_end=2)
        self.assertEqual(result, (0, 2, 0, 2))

    def test_exact_match_in_middle(self):
        """Test finding an extent that matches in the middle of the image."""
        block_size = 1024
        # Image: AAA BBB CCC DDD
        self.image_file.write_bytes(b"A" * block_size + b"B" * block_size +
                                     b"C" * block_size + b"D" * block_size)

        # File: BBB CCC (should match at position 1)
        self.test_file.write_bytes(b"B" * block_size + b"C" * block_size)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        result = self._call_find_extent(processor, self.test_file, file_hashes, 2)

        # Should return (file_start=0, file_end=2, image_start=1, image_end=3)
        self.assertEqual(result, (0, 2, 1, 3))

    def test_exact_match_at_end(self):
        """Test finding an extent that matches at the end of the image."""
        block_size = 1024
        # Image: AAA BBB CCC
        self.image_file.write_bytes(b"A" * block_size + b"B" * block_size + b"C" * block_size)

        # File: CCC (should match at position 2)
        self.test_file.write_bytes(b"C" * block_size)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        # Should return (file_start=0, file_end=1, image_start=2, image_end=3)
        self.assertEqual(result, (0, 1, 2, 3))

    def test_no_match(self):
        """Test when there is no match in the image."""
        block_size = 1024
        # Image: AAA BBB
        self.image_file.write_bytes(b"A" * block_size + b"B" * block_size)

        # File: CCC (no match)
        self.test_file.write_bytes(b"C" * block_size)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        self.assertIsNone(result)

    def test_file_smaller_than_extent_size(self):
        """Test when file is smaller than the minimum extent size."""
        block_size = 1024
        min_extent_blocks = 4  # 4 blocks minimum

        # Image: AAA BBB CCC DDD
        self.image_file.write_bytes(b"A" * block_size * 4)

        # File: only 2 blocks (smaller than min_extent_blocks)
        self.test_file.write_bytes(b"A" * block_size * 2)

        processor = ImageProcessor(self.image_file, block_size=block_size,
                                   min_extent_size=min_extent_blocks * block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Should return None when file is smaller than extent
        result = self._call_find_extent(processor, self.test_file, file_hashes, min_extent_blocks)

        self.assertIsNone(result)

    def test_file_not_multiple_of_block_size(self):
        """Test when file size is not a multiple of block size."""
        block_size = 1024

        # Image: 3.5 blocks worth of data
        image_data = b"A" * block_size + b"B" * block_size + b"C" * block_size + b"D" * 512
        self.image_file.write_bytes(image_data)

        # File: 1.5 blocks worth of data (should match first 2 blocks)
        file_data = b"A" * block_size + b"B" * 512
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Search for 1 block (should match at position 0 and extend to full file)
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        # Should return (file_start=0, file_end=2, image_start=0, image_end=2)
        self.assertEqual(result, (0, 2, 0, 2))

    def test_image_not_multiple_of_block_size(self):
        """Test when image size is not a multiple of block size."""
        block_size = 1024

        # Image: 2.5 blocks
        image_data = b"A" * block_size + b"B" * block_size + b"C" * 512
        self.image_file.write_bytes(image_data)

        # File: 1 full block matching the first block
        file_data = b"A" * block_size
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        # Should return (file_start=0, file_end=1, image_start=0, image_end=1)
        self.assertEqual(result, (0, 1, 0, 1))

    def test_both_files_not_multiple_of_block_size(self):
        """Test when both image and file are not multiples of block size."""
        block_size = 1024

        # Image: 3.7 blocks
        image_data = b"A" * block_size + b"B" * block_size + b"C" * block_size + b"D" * 700
        self.image_file.write_bytes(image_data)

        # File: 2.3 blocks - first 2 blocks match, partial block doesn't (X vs C)
        file_data = b"A" * block_size + b"B" * block_size + b"X" * 300
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Search for 2 blocks
        result = self._call_find_extent(processor, self.test_file, file_hashes, 2)

        # Should return (file_start=0, file_end=2, image_start=0, image_end=2)
        self.assertEqual(result, (0, 2, 0, 2))

    def test_partial_block_no_match(self):
        """Test that partial blocks with different content don't match."""
        block_size = 1024

        # Image: 1.5 blocks: AAA + BBB (512 bytes)
        image_data = b"A" * block_size + b"B" * 512
        self.image_file.write_bytes(image_data)

        # File: 1.5 blocks: AAA + CCC (512 bytes) - second partial block differs
        file_data = b"A" * block_size + b"C" * 512
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Should match only the first block and stop at the difference
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)
        # Returns (file_start=0, file_end=1, image_start=0, image_end=1)
        self.assertEqual(result, (0, 1, 0, 1))

        # Should NOT match 2 blocks (because second partial blocks differ)
        result = self._call_find_extent(processor, self.test_file, file_hashes, 2)
        self.assertIsNone(result)

    def test_empty_file(self):
        """Test with empty file."""
        block_size = 1024

        # Image: AAA BBB
        self.image_file.write_bytes(b"A" * block_size + b"B" * block_size)

        # File: empty
        self.test_file.write_bytes(b"")

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        self.assertIsNone(result)

    def test_hash_collision_with_byte_verification(self):
        """Test that byte-by-byte verification catches hash collisions."""
        block_size = 1024

        # Create image and file with different content but we'll manually set up the scenario
        image_data = b"A" * block_size + b"B" * block_size
        self.image_file.write_bytes(image_data)

        # Different content that should not match
        file_data = b"C" * block_size
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Should not match because byte verification will fail
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        self.assertIsNone(result)

    def test_multiple_matches_returns_first(self):
        """Test that when multiple matches exist, the first one is returned."""
        block_size = 1024

        # Image: AAA BBB AAA CCC (same block appears twice)
        image_data = b"A" * block_size + b"B" * block_size + b"A" * block_size + b"C" * block_size
        self.image_file.write_bytes(image_data)

        # File: AAA (matches at positions 0 and 2)
        file_data = b"A" * block_size
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        # Should return the first match at position 0, extending 1 block
        self.assertEqual(result, (0, 1, 0, 1))

    def test_large_extent_search(self):
        """Test searching for a large extent (multiple blocks)."""
        block_size = 512
        extent_blocks = 8  # 4KB extent

        # Create image with known pattern
        pattern = b"X" * block_size
        image_data = b"A" * (block_size * 5) + pattern * extent_blocks + b"Z" * (block_size * 5)
        self.image_file.write_bytes(image_data)

        # File with matching extent
        file_data = pattern * extent_blocks
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=extent_blocks * block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        result = self._call_find_extent(processor, self.test_file, file_hashes, extent_blocks)

        # Should find at position 5 (after 5 blocks of 'A'), extending 8 blocks
        self.assertEqual(result, (0, 8, 5, 13))

    def test_file_exactly_min_extent_size(self):
        """Test when file is exactly the minimum extent size."""
        block_size = 1024
        min_extent_blocks = 4

        # Image contains the pattern
        pattern = b"X" * block_size
        image_data = b"A" * (block_size * 2) + pattern * min_extent_blocks + b"B" * (block_size * 2)
        self.image_file.write_bytes(image_data)

        # File is exactly min_extent_blocks size
        file_data = pattern * min_extent_blocks
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size,
                                   min_extent_size=min_extent_blocks * block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        result = self._call_find_extent(processor, self.test_file, file_hashes, min_extent_blocks)

        # Should find at position 2, extending 4 blocks
        self.assertEqual(result, (0, 4, 2, 6))

    def test_single_byte_file(self):
        """Test with a single byte file."""
        block_size = 1024

        # Image: 2KB
        self.image_file.write_bytes(b"A" * (block_size * 2))

        # File: just 1 byte
        self.test_file.write_bytes(b"A")

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Should have 1 hash (partial block)
        self.assertEqual(len(file_hashes), 1)

        # But won't match because the content is different (1 byte vs 1024 bytes)
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        self.assertIsNone(result)

    def test_extent_extension(self):
        """Test that extent is extended beyond the initial search size."""
        block_size = 1024

        # Image: AAA BBB CCC DDD EEE
        image_data = (b"A" * block_size + b"B" * block_size + b"C" * block_size +
                     b"D" * block_size + b"E" * block_size)
        self.image_file.write_bytes(image_data)

        # File: BBB CCC DDD (3 blocks that match in the middle)
        file_data = b"B" * block_size + b"C" * block_size + b"D" * block_size
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Search for only 1 block extent, but it should extend to match all 3 blocks
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        # Should return (file_start=0, file_end=3, image_start=1, image_end=4)
        self.assertEqual(result, (0, 3, 1, 4))

    def test_extent_extension_with_partial_block(self):
        """Test extent extension with partial block at the end."""
        block_size = 1024

        # Image: AAA BBB CCC DDD (full blocks)
        image_data = b"A" * block_size + b"B" * block_size + b"C" * block_size + b"D" * block_size
        self.image_file.write_bytes(image_data)

        # File: BBB CCC + 512 bytes of DDD (2.5 blocks)
        file_data = b"B" * block_size + b"C" * block_size + b"D" * 512
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Search for 1 block, should extend to full file
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        # Should return (file_start=0, file_end=3, image_start=1, image_end=4)
        self.assertEqual(result, (0, 3, 1, 4))

    def test_extent_stops_at_first_mismatch(self):
        """Test that extent extension stops at the first byte mismatch."""
        block_size = 1024

        # Image: AAA BBB CCC DDD
        image_data = b"A" * block_size + b"B" * block_size + b"C" * block_size + b"D" * block_size
        self.image_file.write_bytes(image_data)

        # File: BBB + half CCC + half XXX (content diverges in the middle of block 2)
        file_data = b"B" * block_size + b"C" * 512 + b"X" * 512
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Search for 1 block
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1)

        # Should return (file_start=0, file_end=2, image_start=1, image_end=3)
        self.assertEqual(result, (0, 2, 1, 3))

    def test_find_extent_with_file_start_block(self):
        """Test finding extent starting from a specific block in the file."""
        block_size = 1024

        # Image: AAA BBB CCC DDD
        image_data = b"A" * block_size + b"B" * block_size + b"C" * block_size + b"D" * block_size
        self.image_file.write_bytes(image_data)

        # File: AAA BBB CCC (3 blocks)
        file_data = b"A" * block_size + b"B" * block_size + b"C" * block_size
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Search starting from block 1 in the file (BBB)
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1, file_start_block=1)

        # Should return (file_start=1, file_end=3, image_start=1, image_end=3)
        self.assertEqual(result, (1, 3, 1, 3))

    def test_find_extent_with_file_start_block_no_match(self):
        """Test that file_start_block correctly limits search range."""
        block_size = 1024

        # Image: AAA BBB
        image_data = b"A" * block_size + b"B" * block_size
        self.image_file.write_bytes(image_data)

        # File: AAA BBB CCC (only AAA BBB are in the image)
        file_data = b"A" * block_size + b"B" * block_size + b"C" * block_size
        self.test_file.write_bytes(file_data)

        processor = ImageProcessor(self.image_file, block_size=block_size, min_extent_size=block_size)
        file_hashes = processor._generate_hashes_for_file(self.test_file)

        # Search starting from block 2 in the file (CCC) - should not find match
        result = self._call_find_extent(processor, self.test_file, file_hashes, 1, file_start_block=2)

        # Should return None because CCC is not in the image
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
