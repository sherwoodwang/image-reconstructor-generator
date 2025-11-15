"""Tests for OffsetMapper class."""

import unittest
from image_reconstructor_generator import OffsetMapper


class TestOffsetMapper(unittest.TestCase):
    """Test the OffsetMapper class for efficient offset mapping."""

    def test_single_contiguous_range(self):
        """Test with a single contiguous range starting at 0."""
        mapper = OffsetMapper([(0, 100)])

        # Test boundaries
        self.assertEqual(mapper.map_offset(0), 0)
        self.assertEqual(mapper.map_offset(99), 99)

        # Test middle values
        self.assertEqual(mapper.map_offset(50), 50)
        self.assertEqual(mapper.map_offset(1), 1)
        self.assertEqual(mapper.map_offset(98), 98)

    def test_single_range_not_starting_at_zero(self):
        """Test with a single range that doesn't start at 0."""
        mapper = OffsetMapper([(100, 200)])

        # Should map 100-199 to 0-99
        self.assertEqual(mapper.map_offset(100), 0)
        self.assertEqual(mapper.map_offset(150), 50)
        self.assertEqual(mapper.map_offset(199), 99)

    def test_multiple_non_overlapping_ranges(self):
        """Test with multiple non-overlapping ranges."""
        mapper = OffsetMapper([
            (100, 200),   # Maps to 0-99
            (500, 600),   # Maps to 100-199
            (1000, 1500)  # Maps to 200-699
        ])

        # First range
        self.assertEqual(mapper.map_offset(100), 0)
        self.assertEqual(mapper.map_offset(150), 50)
        self.assertEqual(mapper.map_offset(199), 99)

        # Second range
        self.assertEqual(mapper.map_offset(500), 100)
        self.assertEqual(mapper.map_offset(550), 150)
        self.assertEqual(mapper.map_offset(599), 199)

        # Third range
        self.assertEqual(mapper.map_offset(1000), 200)
        self.assertEqual(mapper.map_offset(1250), 450)
        self.assertEqual(mapper.map_offset(1499), 699)

    def test_many_small_ranges(self):
        """Test with many small ranges to verify binary search performance."""
        ranges = [(i * 100, i * 100 + 50) for i in range(100)]
        mapper = OffsetMapper(ranges)

        # Test first range
        self.assertEqual(mapper.map_offset(0), 0)
        self.assertEqual(mapper.map_offset(49), 49)

        # Test middle range (range 50: offsets 5000-5049)
        self.assertEqual(mapper.map_offset(5000), 2500)
        self.assertEqual(mapper.map_offset(5025), 2525)

        # Test last range (range 99: offsets 9900-9949)
        self.assertEqual(mapper.map_offset(9900), 4950)
        self.assertEqual(mapper.map_offset(9949), 4999)

    def test_single_byte_ranges(self):
        """Test with ranges containing single bytes."""
        mapper = OffsetMapper([
            (10, 11),    # Maps to 0
            (20, 21),    # Maps to 1
            (30, 31)     # Maps to 2
        ])

        self.assertEqual(mapper.map_offset(10), 0)
        self.assertEqual(mapper.map_offset(20), 1)
        self.assertEqual(mapper.map_offset(30), 2)

    def test_large_range_values(self):
        """Test with large offset values (GB-scale)."""
        GB = 1024 * 1024 * 1024
        mapper = OffsetMapper([
            (0, 2 * GB),
            (3 * GB, 4 * GB),
            (5 * GB, 6 * GB)
        ])

        # First range
        self.assertEqual(mapper.map_offset(0), 0)
        self.assertEqual(mapper.map_offset(GB), GB)
        self.assertEqual(mapper.map_offset(2 * GB - 1), 2 * GB - 1)

        # Second range (starts at concat offset 2GB)
        self.assertEqual(mapper.map_offset(3 * GB), 2 * GB)
        self.assertEqual(mapper.map_offset(3 * GB + 500), 2 * GB + 500)

        # Third range (starts at concat offset 3GB)
        self.assertEqual(mapper.map_offset(5 * GB), 3 * GB)
        self.assertEqual(mapper.map_offset(5 * GB + 1000), 3 * GB + 1000)

    def test_offset_before_first_range_raises_error(self):
        """Test that offsets before the first range raise ValueError."""
        mapper = OffsetMapper([(100, 200)])

        with self.assertRaises(ValueError) as context:
            mapper.map_offset(50)

        self.assertIn("not found in any mapped range", str(context.exception))
        self.assertIn("50", str(context.exception))

    def test_offset_after_last_range_raises_error(self):
        """Test that offsets after the last range raise ValueError."""
        mapper = OffsetMapper([(100, 200)])

        with self.assertRaises(ValueError) as context:
            mapper.map_offset(250)

        self.assertIn("not found in any mapped range", str(context.exception))
        self.assertIn("250", str(context.exception))

    def test_offset_in_gap_between_ranges_raises_error(self):
        """Test that offsets in gaps between ranges raise ValueError."""
        mapper = OffsetMapper([
            (100, 200),
            (500, 600)
        ])

        # Test offset in gap
        with self.assertRaises(ValueError) as context:
            mapper.map_offset(300)

        self.assertIn("not found in any mapped range", str(context.exception))

    def test_offset_at_range_boundary_end_raises_error(self):
        """Test that offsets at the end boundary (exclusive) raise ValueError."""
        mapper = OffsetMapper([(100, 200)])

        # 200 is the end of the range (exclusive), so it should raise
        with self.assertRaises(ValueError) as context:
            mapper.map_offset(200)

        self.assertIn("not found in any mapped range", str(context.exception))

    def test_empty_ranges_list(self):
        """Test behavior with empty ranges list."""
        mapper = OffsetMapper([])

        # Any offset should raise ValueError
        with self.assertRaises(ValueError):
            mapper.map_offset(0)

        with self.assertRaises(ValueError):
            mapper.map_offset(100)

    def test_ranges_already_sorted(self):
        """Test with ranges that are already sorted."""
        mapper = OffsetMapper([
            (0, 100),
            (200, 300),
            (400, 500)
        ])

        self.assertEqual(mapper.map_offset(50), 50)
        self.assertEqual(mapper.map_offset(250), 150)
        self.assertEqual(mapper.map_offset(450), 250)

    def test_adjacent_ranges(self):
        """Test with ranges that are adjacent (no gaps)."""
        mapper = OffsetMapper([
            (0, 100),
            (100, 200),
            (200, 300)
        ])

        # Verify boundaries work correctly
        self.assertEqual(mapper.map_offset(0), 0)
        self.assertEqual(mapper.map_offset(99), 99)
        self.assertEqual(mapper.map_offset(100), 100)
        self.assertEqual(mapper.map_offset(199), 199)
        self.assertEqual(mapper.map_offset(200), 200)
        self.assertEqual(mapper.map_offset(299), 299)

    def test_binary_search_efficiency(self):
        """Test that binary search works correctly with many ranges."""
        # Create 1000 ranges
        ranges = [(i * 1000, i * 1000 + 500) for i in range(1000)]
        mapper = OffsetMapper(ranges)

        # Test various offsets across the ranges
        # Range 0: 0-499 -> concat 0-499
        self.assertEqual(mapper.map_offset(0), 0)
        self.assertEqual(mapper.map_offset(499), 499)

        # Range 500: 500000-500499 -> concat 250000-250499
        self.assertEqual(mapper.map_offset(500000), 250000)
        self.assertEqual(mapper.map_offset(500250), 250250)

        # Range 999: 999000-999499 -> concat 499500-499999
        self.assertEqual(mapper.map_offset(999000), 499500)
        self.assertEqual(mapper.map_offset(999499), 499999)

    def test_segments_storage_structure(self):
        """Test that segments are stored correctly internally."""
        mapper = OffsetMapper([
            (100, 200),
            (500, 700),
            (1000, 1100)
        ])

        # Verify internal structure
        self.assertEqual(len(mapper.segments), 3)
        self.assertEqual(len(mapper.start_offsets), 3)

        # Check segments content
        self.assertEqual(mapper.segments[0], (100, 200, 0))
        self.assertEqual(mapper.segments[1], (500, 700, 100))
        self.assertEqual(mapper.segments[2], (1000, 1100, 300))

        # Check start_offsets
        self.assertEqual(mapper.start_offsets, [100, 500, 1000])

    def test_cumulative_offset_calculation(self):
        """Test that cumulative offsets are calculated correctly."""
        mapper = OffsetMapper([
            (0, 1000),      # 1000 bytes -> concat 0-999
            (2000, 2500),   # 500 bytes -> concat 1000-1499
            (5000, 5100),   # 100 bytes -> concat 1500-1599
            (10000, 11000)  # 1000 bytes -> concat 1600-2599
        ])

        # Verify cumulative offsets
        self.assertEqual(mapper.map_offset(0), 0)
        self.assertEqual(mapper.map_offset(2000), 1000)
        self.assertEqual(mapper.map_offset(5000), 1500)
        self.assertEqual(mapper.map_offset(10000), 1600)

        # Verify end of each range
        self.assertEqual(mapper.map_offset(999), 999)
        self.assertEqual(mapper.map_offset(2499), 1499)
        self.assertEqual(mapper.map_offset(5099), 1599)
        self.assertEqual(mapper.map_offset(10999), 2599)

    def test_stress_test_many_lookups(self):
        """Stress test with many sequential lookups."""
        ranges = [(i * 100, i * 100 + 50) for i in range(100)]
        mapper = OffsetMapper(ranges)

        # Perform many lookups
        concat_offset = 0
        for i in range(100):
            for j in range(50):
                image_offset = i * 100 + j
                self.assertEqual(mapper.map_offset(image_offset), concat_offset)
                concat_offset += 1


class TestOffsetMapperEdgeCases(unittest.TestCase):
    """Test edge cases for OffsetMapper."""

    def test_zero_length_range_not_created(self):
        """Test that ranges with zero length would be handled correctly."""
        # Note: In actual usage, zero-length ranges shouldn't be created,
        # but if they are, they should be handled gracefully
        mapper = OffsetMapper([
            (100, 100),  # Zero-length range
            (200, 300)
        ])

        # The zero-length range should not contribute to concatenated offset
        # Offset 200 should map to concat offset 0 (not affected by zero-length range)
        self.assertEqual(mapper.map_offset(200), 0)
        self.assertEqual(mapper.map_offset(299), 99)

    def test_very_large_number_of_ranges(self):
        """Test with a very large number of ranges to verify scalability."""
        # Create 10,000 small ranges
        ranges = [(i * 10, i * 10 + 5) for i in range(10000)]
        mapper = OffsetMapper(ranges)

        # Verify the mapper was created
        self.assertEqual(len(mapper.segments), 10000)

        # Test a few lookups
        # Each range is 5 bytes, so total size is 10000 * 5 = 50000 bytes
        self.assertEqual(mapper.map_offset(0), 0)
        self.assertEqual(mapper.map_offset(50000), 25000)
        # Last range is (99990, 99995), so max valid offset is 99994
        self.assertEqual(mapper.map_offset(99994), 49999)

    def test_max_int_range_values(self):
        """Test with very large integer values near system limits."""
        # Use large values (but not quite max int to avoid overflow)
        large_val = 2**50
        mapper = OffsetMapper([
            (large_val, large_val + 1000),
            (large_val + 5000, large_val + 6000)
        ])

        self.assertEqual(mapper.map_offset(large_val), 0)
        self.assertEqual(mapper.map_offset(large_val + 500), 500)
        self.assertEqual(mapper.map_offset(large_val + 5000), 1000)
        self.assertEqual(mapper.map_offset(large_val + 5999), 1999)


if __name__ == '__main__':
    unittest.main()
