#!/usr/bin/env python3
"""
Image Rebuilder - Creates shell scripts to rebuild image files

This tool reads a list of files and generates a POSIX shell script that can
rebuild an image file from the extracted files.
"""

import argparse
import sys
from pathlib import Path
import mmh3


class ImageProcessor:
    """Processes files and generates shell script to rebuild an image."""

    def __init__(self, image_file: Path, output_stream=sys.stdout, block_size: int = 4096, min_extent_size: int = 1048576):
        """
        Initialize the image processor.

        Args:
            image_file: Path to the original image file
            output_stream: Stream to write the shell script to
            block_size: Size of blocks in bytes for hashing (default: 4096)
            min_extent_size: Minimum reusable extent size in bytes (default: 1048576, which is 1 MiB)
        """
        self.image_file = image_file
        self.block_size = block_size
        self.min_extent_size = min_extent_size
        self.min_extent_blocks = min_extent_size // block_size
        self.output_stream = output_stream
        self.image_hashes = self._generate_image_hashes()

    def _generate_hashes_for_file(self, file_path):
        """
        Generate an array of murmur hashes for each block in a file.

        Args:
            file_path: Path to the file to hash

        Returns:
            List of hash values for each block in the file
        """
        hashes = []
        with open(file_path, 'rb') as f:
            while True:
                block = f.read(self.block_size)
                if not block:
                    break
                # Use MurmurHash3 to hash the block
                hash_value = mmh3.hash(block, signed=False)
                hashes.append(hash_value)
        return hashes

    def _generate_image_hashes(self):
        """
        Generate an in-memory array of murmur hashes for each block in the image.

        Returns:
            List of hash values for each block in the image
        """
        return self._generate_hashes_for_file(self.image_file)

    def begin(self):
        """Start processing - write shell script header."""
        # TODO: Implement shell script header generation
        pass

    def _find_extent_in_image(self, file_f, image_f, file_size, image_size,
                              file_hashes, extent_blocks, file_start_block=0):
        """
        Find the first occurrence of an extent (sequence of hashes) in the image
        and extend it as far as possible using byte-by-byte comparison.

        Args:
            file_f: Open file handle for the file being searched
            image_f: Open file handle for the image file
            file_size: Size of the file in bytes
            image_size: Size of the image in bytes
            file_hashes: List of hash values from the file
            extent_blocks: Number of blocks in the extent to search for
            file_start_block: Block offset in the file to start searching from (default: 0)

        Returns:
            Tuple of (file_start_block, file_end_block, image_start_block, image_end_block) where:
            - file_start_block: Starting block in the file that matched
            - file_end_block: Ending block in the file (exclusive)
            - image_start_block: Starting block in the image where match was found
            - image_end_block: Ending block in the image (exclusive)
            Returns None if not found.
        """
        if file_start_block + extent_blocks > len(file_hashes):
            return None

        # Extract the extent starting from file_start_block
        extent = file_hashes[file_start_block:file_start_block + extent_blocks]

        # Search for this extent in the image hashes
        # We need to find a contiguous sequence of hashes that matches
        for i in range(len(self.image_hashes) - extent_blocks + 1):
            # Check if all hashes in the extent match at this position
            if self.image_hashes[i:i + extent_blocks] == extent:
                # Hash match found - verify and extend by byte-by-byte comparison
                result = self._extend_match_forward_at_offset(
                    file_f, image_f, file_size, image_size,
                    file_start_block, i, extent_blocks
                )

                if result is not None:
                    # Match confirmed and extends at least the minimum extent size
                    file_end_block, image_end_block = result
                    return (file_start_block, file_end_block, i, image_end_block)
                # Hash collision or match too short - continue searching

        return None

    def _extend_match_forward_at_offset(self, file_f, image_f, file_size, image_size,
                                        file_start_block, image_start_block, min_extent_blocks):
        """
        Verify and extend a matched region as far as possible by byte-by-byte comparison.

        Args:
            file_f: Open file handle for the file being compared
            image_f: Open file handle for the image file
            file_size: Size of the file in bytes
            image_size: Size of the image in bytes
            file_start_block: Starting block in the file
            image_start_block: Starting block in the image
            min_extent_blocks: Minimum number of blocks required for a valid extent

        Returns:
            Tuple of (file_end_block, image_end_block) if match extends at least min_extent_blocks,
            None otherwise
        """
        # Calculate byte offsets from the start of the match
        file_offset = file_start_block * self.block_size
        image_offset = image_start_block * self.block_size

        # Maximum bytes we can compare
        max_file_bytes = file_size - file_offset
        max_image_bytes = image_size - image_offset

        if max_file_bytes <= 0 or max_image_bytes <= 0:
            # Nothing to compare
            return None

        # Seek to the starting positions
        file_f.seek(file_offset)
        image_f.seek(image_offset)

        chunk_size = 65536  # 64KB chunks for efficiency
        bytes_matched = 0
        max_bytes = min(max_file_bytes, max_image_bytes)

        while bytes_matched < max_bytes:
            bytes_to_read = min(chunk_size, max_bytes - bytes_matched)

            file_chunk = file_f.read(bytes_to_read)
            image_chunk = image_f.read(bytes_to_read)

            # Find how many bytes match in this chunk
            for j in range(len(file_chunk)):
                if j >= len(image_chunk) or file_chunk[j] != image_chunk[j]:
                    # Mismatch found
                    bytes_matched += j
                    # Calculate total matched bytes from the start
                    total_file_bytes = file_offset + bytes_matched
                    total_image_bytes = image_offset + bytes_matched
                    # Round up to include any partial block
                    file_end_block = (total_file_bytes + self.block_size - 1) // self.block_size
                    image_end_block = (total_image_bytes + self.block_size - 1) // self.block_size

                    # Check if we met the minimum extent requirement
                    if file_end_block - file_start_block >= min_extent_blocks:
                        return file_end_block, image_end_block
                    else:
                        return None

            # All bytes in this chunk matched
            bytes_matched += len(file_chunk)

            if len(file_chunk) < bytes_to_read:
                # Reached end of file
                break

        # Everything matched to the end
        total_file_bytes = file_offset + bytes_matched
        total_image_bytes = image_offset + bytes_matched
        file_end_block = (total_file_bytes + self.block_size - 1) // self.block_size
        image_end_block = (total_image_bytes + self.block_size - 1) // self.block_size

        # Check if we met the minimum extent requirement
        if file_end_block - file_start_block >= min_extent_blocks:
            return file_end_block, image_end_block
        else:
            return None

    def process_file(self, file_path: str):
        """
        Process a single file from the input list.

        Args:
            file_path: Path to the file to process
        """
        # Verify the file exists and is accessible
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not file_path_obj.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        # Generate hash array for this file
        file_hashes = self._generate_hashes_for_file(file_path_obj)

        # Get file sizes
        file_size = file_path_obj.stat().st_size
        image_size = self.image_file.stat().st_size

        # Open files once for the entire processing loop
        with open(file_path_obj, 'rb') as file_f, open(self.image_file, 'rb') as image_f:
            # Process the file in a loop, finding matches and handling unmatched sections
            current_block = 0

            while current_block < len(file_hashes):
                # Search for the next occurrence of the minimum extent in the image
                match_result = self._find_extent_in_image(
                    file_f, image_f, file_size, image_size,
                    file_hashes, self.min_extent_blocks, current_block
                )

                if match_result is not None:
                    # Found a match - match_result is (file_start_block, file_end_block, image_start_block, image_end_block)
                    file_start_block, file_end_block, image_start_block, image_end_block = match_result

                    file_start_byte = file_start_block * self.block_size
                    file_end_byte = file_end_block * self.block_size
                    image_start_byte = image_start_block * self.block_size
                    image_end_byte = image_end_block * self.block_size

                    # TODO: Generate shell script commands to extract this extent from the image
                    # For now, just continue processing

                    # Continue from the end of this match
                    current_block = file_end_block
                else:
                    # No match found - skip forward by minimum extent size
                    current_block += self.min_extent_blocks

                    # TODO: Handle the unmatched section (will need to be included literally in output)

    def finalize(self):
        """Finish processing - write shell script footer."""
        # TODO: Implement shell script footer generation
        pass


def read_file_list(input_stream, null_separated: bool):
    """
    Read file list from input stream.

    Args:
        input_stream: Input stream to read from (stdin or file)
        null_separated: If True, expect null-separated files; otherwise newline-separated

    Yields:
        File paths from the input
    """
    if null_separated:
        # Read null-separated entries
        buffer = ""
        while True:
            chunk = input_stream.read(4096)
            if not chunk:
                if buffer:
                    yield buffer
                break

            buffer += chunk
            while '\0' in buffer:
                entry, buffer = buffer.split('\0', 1)
                if entry:
                    yield entry
    else:
        # Read newline-separated entries
        for line in input_stream:
            line = line.rstrip('\n\r')
            if line:
                yield line


def main():
    """Main entry point for the image rebuilder."""
    parser = argparse.ArgumentParser(
        description='Generate a shell script to rebuild an image file from extracted files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From newline-separated file list
  find extracted_dir -type f | %(prog)s original.img > rebuild.sh

  # From null-separated file list (handles special characters)
  find extracted_dir -type f -print0 | %(prog)s -0 original.img > rebuild.sh

  # From a saved file list
  %(prog)s original.img -i files.txt > rebuild.sh
        """
    )

    parser.add_argument(
        'image',
        type=Path,
        help='Path to the original image file'
    )

    parser.add_argument(
        '-i', '--input',
        type=argparse.FileType('r'),
        default=sys.stdin,
        metavar='FILE',
        help='Read file list from FILE instead of stdin'
    )

    parser.add_argument(
        '-0', '--null',
        action='store_true',
        help='File list is null-separated (like find -print0) instead of newline-separated'
    )

    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'),
        default=sys.stdout,
        metavar='FILE',
        help='Write shell script to FILE instead of stdout'
    )

    parser.add_argument(
        '--force-terminal-output',
        action='store_true',
        help='Allow writing binary data to terminal (use with caution)'
    )

    parser.add_argument(
        '-b', '--block-size',
        type=int,
        default=4096,
        metavar='BYTES',
        help='Block size in bytes for hashing (default: 4096, which is 4KB)'
    )

    parser.add_argument(
        '-m', '--min-extent-size',
        type=int,
        default=1048576,
        metavar='BYTES',
        help='Minimum reusable extent size in bytes (must be a multiple of block size, default: 1048576, which is 1 MiB)'
    )

    args = parser.parse_args()

    # Validate min-extent-size is a multiple of block-size
    if args.min_extent_size % args.block_size != 0:
        parser.error(f"Minimum extent size ({args.min_extent_size}) must be a multiple of block size ({args.block_size})")

    # Verify the image file exists
    if not args.image.exists():
        parser.error(f"Image file does not exist: {args.image}")

    if not args.image.is_file():
        parser.error(f"Image path is not a file: {args.image}")

    # Check if output is a terminal (not redirected)
    # The output contains binary data that shouldn't be printed to terminal
    if args.output == sys.stdout and args.output.isatty() and not args.force_terminal_output:
        parser.error(
            "Refusing to write binary data to terminal.\n"
            "Please redirect output to a file using:\n"
            "  - Shell redirection: %(prog)s ... > output.sh\n"
            "  - Or use the -o option: %(prog)s ... -o output.sh\n"
            "  - Or force terminal output: %(prog)s ... --force-terminal-output"
        )

    # Initialize the processor
    processor = ImageProcessor(args.image, args.output, block_size=args.block_size, min_extent_size=args.min_extent_size)

    try:
        # Begin processing
        processor.begin()

        # Process each file in the input list
        file_count = 0
        for file_path in read_file_list(args.input, args.null):
            processor.process_file(file_path)
            file_count += 1

        # Finalize the script
        processor.finalize()

        # Print summary to stderr
        print(f"Processed {file_count} files", file=sys.stderr)

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if args.input != sys.stdin:
            args.input.close()
        if args.output != sys.stdout:
            args.output.close()


if __name__ == '__main__':
    main()
