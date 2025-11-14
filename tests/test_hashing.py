#!/usr/bin/env python3
"""
Tests for block hashing functionality.
"""

import unittest
import tempfile
import sys
from pathlib import Path
import mmh3

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from image_rebuilder import ImageProcessor


class TestBlockSizeAndHashing(unittest.TestCase):
    """Tests for block size parameter and hash generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_file = Path(self.temp_dir.name) / "test.img"

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_default_block_size(self):
        """Test that default block size is 4096 bytes (4KB)."""
        self.image_file.write_bytes(b"A" * 5000)
        processor = ImageProcessor(self.image_file)

        self.assertEqual(processor.block_size, 4096)

    def test_custom_block_size(self):
        """Test that custom block size is applied."""
        self.image_file.write_bytes(b"A" * 5000)
        processor = ImageProcessor(self.image_file, block_size=1024)

        self.assertEqual(processor.block_size, 1024)

    def test_hash_generation_default_block_size(self):
        """Test hash generation with default block size."""
        # Create a 10KB file (will be split into 3 blocks: 4KB, 4KB, 2KB)
        self.image_file.write_bytes(b"A" * 10240)
        processor = ImageProcessor(self.image_file)

        self.assertEqual(len(processor.image_hashes), 3)
        # Verify all hashes are unsigned integers
        for hash_value in processor.image_hashes:
            self.assertIsInstance(hash_value, int)
            self.assertGreaterEqual(hash_value, 0)
            self.assertLess(hash_value, 2**32)

    def test_hash_generation_custom_block_size(self):
        """Test hash generation with custom block size."""
        # Create a 5KB file with 1KB blocks (will be split into 5 blocks)
        self.image_file.write_bytes(b"A" * 5120)
        processor = ImageProcessor(self.image_file, block_size=1024)

        self.assertEqual(len(processor.image_hashes), 5)

    def test_hash_values_are_consistent(self):
        """Test that hash values are consistent for the same content."""
        # Create a file with known content
        content = b"A" * 4096
        self.image_file.write_bytes(content)

        # Get hash from processor
        processor = ImageProcessor(self.image_file)

        # Calculate expected hash directly
        expected_hash = mmh3.hash(content, signed=False)

        self.assertEqual(processor.image_hashes[0], expected_hash)

    def test_different_blocks_have_different_hashes(self):
        """Test that different blocks produce different hashes."""
        # Create a file with distinct blocks
        block1 = b"A" * 1024
        block2 = b"B" * 1024
        block3 = b"C" * 1024
        self.image_file.write_bytes(block1 + block2 + block3)

        processor = ImageProcessor(self.image_file, block_size=1024)

        # All three hashes should be different
        self.assertEqual(len(processor.image_hashes), 3)
        self.assertNotEqual(processor.image_hashes[0], processor.image_hashes[1])
        self.assertNotEqual(processor.image_hashes[1], processor.image_hashes[2])
        self.assertNotEqual(processor.image_hashes[0], processor.image_hashes[2])

    def test_empty_image_file(self):
        """Test hash generation with empty image file."""
        self.image_file.write_bytes(b"")
        processor = ImageProcessor(self.image_file)

        self.assertEqual(len(processor.image_hashes), 0)

    def test_image_smaller_than_block_size(self):
        """Test hash generation when image is smaller than block size."""
        # Create a 100-byte file with 4KB block size
        self.image_file.write_bytes(b"X" * 100)
        processor = ImageProcessor(self.image_file)

        # Should have exactly one block (partial block)
        self.assertEqual(len(processor.image_hashes), 1)

    def test_image_exactly_one_block(self):
        """Test hash generation when image is exactly one block."""
        self.image_file.write_bytes(b"Y" * 4096)
        processor = ImageProcessor(self.image_file)

        self.assertEqual(len(processor.image_hashes), 1)

    def test_image_exactly_multiple_blocks(self):
        """Test hash generation when image is exactly multiple blocks."""
        self.image_file.write_bytes(b"Z" * 8192)  # Exactly 2 blocks
        processor = ImageProcessor(self.image_file)

        self.assertEqual(len(processor.image_hashes), 2)


if __name__ == '__main__':
    unittest.main()
