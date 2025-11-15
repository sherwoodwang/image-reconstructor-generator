#!/usr/bin/env python3
"""
Image Rebuilder - Creates shell scripts to rebuild image files

This tool reads a list of files and generates a POSIX shell script that can
rebuild an image file from the extracted files.
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple, Optional
import mmh3
import hashlib
import os
import pwd
import grp
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from datetime import datetime
import bisect


def escape_for_shell_display(path: str) -> str:
    """
    Escape a file path for safe display in POSIX shell scripts.

    Uses single quotes ('xxx') for all content. Single quotes preserve everything
    literally including newlines, tabs, backslashes, and other special characters.
    The only character that needs escaping is the single quote itself, which is
    escaped as '"'"' (end quote, escaped quote, start quote).

    This function ensures that the escaped string, when evaluated by a POSIX
    shell, will produce exactly the original path string.

    Args:
        path: The file path string to escape

    Returns:
        A shell-escaped string

    Examples:
        >>> escape_for_shell_display("simple.txt")
        "'simple.txt'"
        >>> escape_for_shell_display("file with spaces.txt")
        "'file with spaces.txt'"
        >>> escape_for_shell_display("file'with'quotes.txt")
        "'file'\"'\"'with'\"'\"'quotes.txt'"
        >>> escape_for_shell_display("file\\nwith\\nbackslash")
        "'file\\nwith\\nbackslash'"
    """
    if not path:
        return "''"

    # Single quotes preserve everything literally, including newlines, tabs,
    # backslashes, and all other special characters. The only character that
    # needs escaping is the single quote itself.
    if "'" in path:
        # Replace ' with '"'"' (end quote, escaped quote, start quote)
        escaped = path.replace("'", "'\"'\"'")
        return f"'{escaped}'"
    else:
        # No single quotes, just wrap in single quotes
        return f"'{path}'"


class OffsetMapper:
    """Maps image offsets to concatenated data offsets using binary search.

    This avoids creating a massive dictionary for large files by preprocessing
    the image ranges into a compact representation that supports O(log n) lookups.
    """

    def __init__(self, image_ranges: list[tuple[int, int]]):
        """Initialize the mapper with a list of (start_offset, end_offset) tuples.

        Args:
            image_ranges: List of (image_start, image_end) tuples representing
                         contiguous ranges from the image file.
        """
        # Store the ranges and compute cumulative offsets
        # Each entry: (image_start, image_end, concat_start)
        self.segments: list[tuple[int, int, int]] = []
        concatenated_offset = 0

        for start_offset, end_offset in image_ranges:
            segment_size = end_offset - start_offset
            self.segments.append((start_offset, end_offset, concatenated_offset))
            concatenated_offset += segment_size

        # Extract start offsets for binary search
        self.start_offsets = [seg[0] for seg in self.segments]

    def map_offset(self, image_offset: int) -> int:
        """Map an image offset to its corresponding concatenated data offset.

        Args:
            image_offset: Offset in the original image file

        Returns:
            Corresponding offset in the concatenated data

        Raises:
            ValueError: If the image_offset is not within any mapped range
        """
        # Binary search to find the segment containing this offset
        idx = bisect.bisect_right(self.start_offsets, image_offset) - 1

        if idx < 0 or idx >= len(self.segments):
            raise ValueError(f"Image offset {image_offset} not found in any mapped range")

        image_start, image_end, concat_start = self.segments[idx]

        # Verify the offset is within this segment
        if image_offset < image_start or image_offset >= image_end:
            raise ValueError(f"Image offset {image_offset} not found in any mapped range")

        # Calculate the concatenated offset
        return concat_start + (image_offset - image_start)


class ImageInfo(NamedTuple):
    """Information about the image file."""
    size: int
    permissions: int
    uid: int
    gid: int
    owner: str
    group: str
    atime: float
    mtime: float
    ctime: float
    md5: str
    sha256: str
    acl: Optional[str]  # Extended ACL information if available


class ImageProcessor:
    """Processes files and generates shell script to rebuild an image."""

    def __init__(self, image_file: Path, output_stream=sys.stdout, block_size: int = 4096, min_extent_size: int = 1048576,
                 capture_ownership: bool = True, capture_acl: bool = True, capture_md5: bool = True, capture_sha256: bool = True,
                 verbose: bool = False, write_chunk_size: int = 16*1024*1024):
        """
        Initialize the image processor.

        Args:
            image_file: Path to the original image file
            output_stream: Stream to write the shell script to
            block_size: Size of blocks in bytes for hashing (default: 4096)
            min_extent_size: Minimum reusable extent size in bytes (default: 1048576, which is 1 MiB)
            capture_ownership: Whether to capture ownership information for the image file (default: True)
            capture_acl: Whether to capture ACL information for the image file (default: True)
            capture_md5: Whether to calculate MD5 hash for the image file (default: True)
            capture_sha256: Whether to calculate SHA256 hash for the image file (default: True)
            verbose: Whether to print timestamped progress messages to stderr (default: False)
            write_chunk_size: Size of chunks in bytes for writing attachment data (default: 16 MiB)
        """
        self.image_file = image_file
        self.block_size = block_size
        self.min_extent_size = min_extent_size
        self.min_extent_blocks = max(1, min_extent_size // block_size)
        self.output_stream = output_stream
        self.capture_ownership = capture_ownership
        self.capture_acl = capture_acl
        self.capture_md5 = capture_md5
        self.capture_sha256 = capture_sha256
        self.verbose = verbose
        self.write_chunk_size = write_chunk_size
        self.image_hashes: list[int] = []
        self.image_info: ImageInfo
        self.matches = []  # List of (file_path, file_start_byte, file_end_byte, image_start_byte, image_end_byte) tuples
        self.file_count = 0  # Track number of processed files
        self._initialize()

    def _log(self, message: str):
        """Print a timestamped message to stderr if verbose mode is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print(f"[{timestamp}] {message}", file=sys.stderr)

    def _initialize(self):
        """
        Initialize the image processor by generating image hashes and gathering image metadata.

        This is called automatically at the end of __init__.
        """
        # Gather image file information
        stat_info = self.image_file.stat()

        # Get owner and group names (if requested)
        if self.capture_ownership:
            try:
                owner = pwd.getpwuid(stat_info.st_uid).pw_name
            except KeyError:
                owner = str(stat_info.st_uid)

            try:
                group = grp.getgrgid(stat_info.st_gid).gr_name
            except KeyError:
                group = str(stat_info.st_gid)
        else:
            owner = ""
            group = ""

        # Try to get ACL information (if requested and available)
        acl_info: Optional[str] = None
        if self.capture_acl:
            try:
                result = subprocess.run(
                    ['getfacl', '-p', str(self.image_file)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    acl_info = result.stdout
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                # getfacl not available or failed, skip ACL
                pass

        # Calculate MD5 and SHA256 hashes using parallel threads for better performance
        # Using hashlib.file_digest() which is optimized and releases the GIL
        md5_result: list[Optional[str]] = [None]
        sha256_result: list[Optional[str]] = [None]

        # Determine which hashes to compute
        compute_hashes = []

        if self.capture_md5 or self.capture_sha256:
            md5_lock = Lock()
            sha256_lock = Lock()

            if self.capture_md5:
                def compute_md5():
                    self._log("Starting MD5 hash generation")
                    with open(self.image_file, 'rb') as f:
                        digest = hashlib.file_digest(f, 'md5')
                    with md5_lock:
                        md5_result[0] = digest.hexdigest()
                    self._log("Completed MD5 hash generation")
                compute_hashes.append(('md5', compute_md5))

            if self.capture_sha256:
                def compute_sha256():
                    self._log("Starting SHA256 hash generation")
                    with open(self.image_file, 'rb') as f:
                        digest = hashlib.file_digest(f, 'sha256')
                    with sha256_lock:
                        sha256_result[0] = digest.hexdigest()
                    self._log("Completed SHA256 hash generation")
                compute_hashes.append(('sha256', compute_sha256))

            # Run hash calculations in parallel
            with ThreadPoolExecutor(max_workers=len(compute_hashes)) as executor:
                futures = [executor.submit(func) for _, func in compute_hashes]
                for future in futures:
                    future.result()

        # Get final hash values (empty string if not computed)
        md5_hash = md5_result[0] if md5_result[0] is not None else ""
        sha256_hash = sha256_result[0] if sha256_result[0] is not None else ""

        self.image_info = ImageInfo(
            size=stat_info.st_size,
            permissions=stat_info.st_mode,
            uid=stat_info.st_uid,
            gid=stat_info.st_gid,
            owner=owner,
            group=group,
            atime=stat_info.st_atime,
            mtime=stat_info.st_mtime,
            ctime=stat_info.st_ctime,
            md5=md5_hash,
            sha256=sha256_hash,
            acl=acl_info
        )

        # Generate block hashes for the image
        self._log("Starting image block hash generation")
        self.image_hashes = self._generate_image_hashes()
        self._log("Completed image block hash generation")

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
        # Canonicalize and validate the file path
        import os

        # Convert to relative path from working directory - this is required since
        # the file_path will be embedded in the generated shell script
        try:
            relative_path = Path(os.path.normpath(os.path.abspath(file_path))).relative_to(Path.cwd())
            relative_path = Path(os.path.normpath(str(relative_path)))
        except (OSError, ValueError) as e:
            raise ValueError(f"Cannot make path '{file_path}' relative to working directory: {e}")

        # Ensure relative_path doesn't contain ..
        if '..' in relative_path.parts:
            raise ValueError(f"Path '{file_path}' contains '..' components that would escape the working directory")

        # Verify the file exists and is accessible
        if not relative_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not relative_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        self._log(f"Processing file: {relative_path}")

        # Generate hash array for this file
        file_hashes = self._generate_hashes_for_file(relative_path)

        # Get file sizes
        file_size = relative_path.stat().st_size
        image_size = os.path.getsize(str(self.image_file))

        # Open files once for the entire processing loop
        with open(relative_path, 'rb') as file_f, open(self.image_file, 'rb') as image_f:
            # Process the file in a loop, finding matches and handling unmatched sections
            current_block = 0
            self._log(f"Starting reusable extent detection for {relative_path} (size: {file_size} bytes)")

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

                    # Register this match with the relative file path
                    self.matches.append((relative_path, file_start_byte, file_end_byte, image_start_byte, image_end_byte))

                    # Log the extent match
                    extent_size = file_end_byte - file_start_byte
                    self._log(f"Found reusable extent: {file_start_byte}-{file_end_byte} ({extent_size} bytes) -> image offset {image_start_byte}")

                    # Continue from the end of this match
                    current_block = file_end_block
                else:
                    # No match found - skip forward by minimum extent size
                    current_block += self.min_extent_blocks

            # Log completion with summary
            current_byte = current_block * self.block_size
            self._log(f"Completed reusable extent detection for {relative_path} (processed: {min(current_byte, file_size)}/{file_size} bytes)")

        # Increment file count
        self.file_count += 1

    def generate_script(self):
        """
        Generate the complete self-extracting reconstruction shell script.

        This method should be called after all files have been processed with process_file().
        It performs the following steps:
        1. Generates the reconstruction sequence from all collected matches
        2. Creates a layout of concatenated data from the image file
        3. Generates the inner shell script for data copying and validation
        4. Creates the self-extracting wrapper script with embedded data
        """
        self._log("Generating reconstruction script")

        # Get the image size
        image_size = self.image_file.stat().st_size

        # Generate the reconstruction sequence
        self._log("Generating reconstruction sequence")
        sequence = generate_reconstruction_sequence(self.matches, image_size)

        # Step 1: Identify all ranges selected from the image and create layout
        # This creates a mapping from original image offsets to concatenated data offsets
        image_ranges = []  # List of (image_start, image_end) tuples

        # First pass: collect all image ranges
        for source, start_offset, end_offset in sequence:
            if source == 'image':
                image_ranges.append((start_offset, end_offset))

        # Second pass: create offset mapping using binary search for efficiency
        offset_mapping = OffsetMapper(image_ranges)

        # Step 2: Generate the inner shell script that will copy bytes to reconstruct the image
        self._log("Generating reconstruction script")
        script_text = self._generate_reconstruction_script(sequence, offset_mapping, self.image_info)

        # Step 3: Generate the self-extracting wrapper script
        self._log("Generating self-extracting shell wrapper")

        # Define progress callback for verbose mode
        def progress_callback(bytes_written: int, total_bytes: int) -> None:
            """Report progress to stderr if verbose mode is enabled."""
            if self.verbose:
                percent = (bytes_written / total_bytes * 100) if total_bytes > 0 else 0
                sys.stderr.write(f"\r[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Writing attachment data: {bytes_written:,} / {total_bytes:,} bytes ({percent:.1f}%)")
                sys.stderr.flush()
                if bytes_written == total_bytes:
                    sys.stderr.write("\n")
                    sys.stderr.flush()

        generate_shell_wrapper(script_text, image_ranges, self.image_file, self.output_stream,
                              progress_callback=progress_callback if self.verbose else None,
                              chunk_size=self.write_chunk_size)
        self._log(f"Processed {self.file_count} files")
        self._log("Script generation complete")

    def _generate_reconstruction_script(self, sequence, offset_mapping: OffsetMapper, image_info: ImageInfo) -> str:
        """Generate the complete reconstruction script with validation and restoration."""
        script_lines = []

        # Extract unique file list from sequence (excluding 'image' entries)
        source_files = sorted(set(source for source, _, _ in sequence if source != 'image'))

        # Script header with usage and argument parsing
        script_lines.extend([
            '# Parse command-line arguments',
            'show_info=0',
            'skip_md5=0',
            'skip_sha256=0',
            'skip_permissions=0',
            'skip_ownership=0',
            'skip_timestamps=0',
            'skip_acl=0',
            'use_tempfile=0',
            'verbose=0',
            'exit_code=0',
            f'block_size={self.write_chunk_size}',
            'dd_mode=""',
            'allow_tty=0',
            'allow_overwrite=0',
            '',
            'usage() {',
            '    cat >&2 <<EOF',
            'Usage: $0 [options] [output-file]',
            '',
            'This is a self-extracting reconstruction script that rebuilds an original file',
            'from embedded binary data and/or external source files. The script reconstructs',
            'the file by copying data segments in the correct order and optionally verifies',
            'checksums and restores file metadata (permissions, ownership, timestamps, ACLs).',
            '',
            'Options:',
            '  -i          Show image information only (do not reconstruct)',
            '  -M          Skip MD5 verification',
            '  -S          Skip SHA256 verification',
            '  -p          Skip permission restoration',
            '  -o          Skip ownership restoration',
            '  -t          Skip timestamp restoration',
            '  -a          Skip ACL restoration',
            '  -T          Use intermediate temporary file for validation',
            '  -v          Verbose mode (show progress messages)',
            f'  -b SIZE     Block size in bytes for dd operations (default: {self.write_chunk_size})',
            '  -x OPTS     Extra options (comma-separated):',
            '                gnu-dd      - Force GNU dd mode (requires iflag support)',
            '                plain-dd    - Force plain dd mode (POSIX compatible)',
            '                no-dd       - Use only tail/head (most portable)',
            '                allow-tty   - Allow binary output to terminal (use with caution)',
            '                overwrite   - Overwrite existing output file if present',
            '  -h          Show this help message',
            '',
            'Arguments:',
            '  output-file Optional output filename (default: stdout)',
            '',
            'Examples:',
            '  $0 -i                          # Show image information',
            '  $0 output.bin                  # Reconstruct to output.bin',
            '  $0 > output.bin                # Reconstruct to stdout',
            '  $0 -M -S output.bin            # Skip checksum verification',
            '  $0 -x overwrite output.bin     # Overwrite existing file',
            '  $0 -x no-dd -v output.bin      # Use portable mode with verbose output',
            'EOF',
            '    exit 1',
            '}',
            '',
            'while getopts "iMSpotaTvb:x:h" opt; do',
            '    case "$opt" in',
            '        i) show_info=1 ;;',
            '        M) skip_md5=1 ;;',
            '        S) skip_sha256=1 ;;',
            '        p) skip_permissions=1 ;;',
            '        o) skip_ownership=1 ;;',
            '        t) skip_timestamps=1 ;;',
            '        a) skip_acl=1 ;;',
            '        T) use_tempfile=1 ;;',
            '        v) verbose=1 ;;',
            '        b) block_size="$OPTARG" ;;',
            '        x)',
            '            # Parse comma-separated extra options',
            '            # Use POSIX-compatible method (no here-string)',
            '            saved_ifs="$IFS"',
            '            IFS=,',
            '            for opt_val in $OPTARG; do',
            '                case "$opt_val" in',
            '                    gnu-dd) dd_mode="gnu" ;;',
            '                    plain-dd) dd_mode="plain" ;;',
            '                    no-dd) dd_mode="none" ;;',
            '                    allow-tty) allow_tty=1 ;;',
            '                    overwrite) allow_overwrite=1 ;;',
            '                    *) echo "Warning: Unknown option: $opt_val" >&2 ;;',
            '                esac',
            '            done',
            '            IFS="$saved_ifs"',
            '            ;;',
            '        h) usage ;;',
            '        *) usage ;;',
            '    esac',
            'done',
            'shift $((OPTIND - 1))',
            '',
            '# Set up metadata variables upfront',
            f'file_perms="{oct(image_info.permissions & 0o777)[2:]}"',
            f'file_mtime="{int(image_info.mtime)}"',
        ])

        if image_info.owner and image_info.group:
            script_lines.extend([
                f'file_owner="{image_info.owner}"',
                f'file_group="{image_info.group}"',
            ])

        if image_info.acl:
            escaped_acl = escape_for_shell_display(image_info.acl)
            script_lines.extend([
                f"file_acl={escaped_acl}",
            ])

        # Set up additional metadata variables for info display
        script_lines.extend([
            f'file_size={image_info.size}',
            f'file_atime={int(image_info.atime)}',
            f'file_ctime={int(image_info.ctime)}',
        ])

        if image_info.md5:
            script_lines.append(f'file_md5="{image_info.md5}"')
        if image_info.sha256:
            script_lines.append(f'file_sha256="{image_info.sha256}"')
        if image_info.uid or image_info.gid:
            script_lines.extend([
                f'file_uid={image_info.uid}',
                f'file_gid={image_info.gid}',
            ])

        script_lines.extend([
            '',
            '# Show information mode',
            'if [ "$show_info" -eq 1 ]; then',
            '    cat <<EOF',
            'Image Information:',
            '  Size:        $file_size bytes',
            '  Permissions: $file_perms',
        ])

        if image_info.owner and image_info.group:
            script_lines.append('  Owner:Group: $file_owner:$file_group')
        if image_info.uid or image_info.gid:
            script_lines.append('  UID:GID:     $file_uid:$file_gid')

        script_lines.extend([
            '  Accessed:    @$file_atime',
            '  Modified:    @$file_mtime',
            '  Changed:     @$file_ctime',
        ])

        if image_info.md5:
            script_lines.append('  MD5:         $file_md5')
        if image_info.sha256:
            script_lines.append('  SHA256:      $file_sha256')
        if image_info.acl:
            script_lines.append('  ACL:         Available')

        # Close heredoc before source files list
        script_lines.extend([
            '',
            'Source Files:',
            'EOF',
        ])

        # Add source files list using echo (not heredoc) for proper escaping
        if source_files:
            for file_path in source_files:
                # Escape the file path for display using secure escaping
                escaped_path = escape_for_shell_display(str(file_path))
                script_lines.append(f"    echo '  '{escaped_path}")
        else:
            script_lines.append("    echo '  (no external files - image reconstructed from embedded data only)'")

        script_lines.extend([
            '    exit 0',
            'fi',
            '',
            'output_file=""',
            'if [ $# -eq 1 ]; then',
            '    output_file="$1"',
            'elif [ $# -gt 1 ]; then',
            '    echo "Error: Too many arguments" >&2',
            '    usage',
            'fi',
            '',
            '# Check if output file already exists',
            'if [ -n "$output_file" ] && [ -e "$output_file" ] && [ "$allow_overwrite" -eq 0 ]; then',
            '    echo "Error: Output file already exists: $output_file" >&2',
            '    echo "Use -x overwrite to overwrite existing files." >&2',
            '    exit 1',
            'fi',
            '',
            '# Check if stdout is a terminal when no output file specified',
            'if [ -z "$output_file" ] && [ -t 1 ] && [ "$allow_tty" -eq 0 ]; then',
            '    echo "Error: Refusing to write binary data to terminal." >&2',
            '    echo "Use -h for usage information, or -x allow-tty to override." >&2',
            '    exit 1',
            'fi',
            '',
            '# Detect dd mode',
            '# Three modes supported:',
            '# - gnu: Use GNU dd with iflag=skip_bytes,count_bytes (fastest, large blocks)',
            '# - plain: Use plain dd with block-wise skip + head/tail for in-block precision',
            '# - none: Use only tail/head, no dd (most portable, slightly slower)',
            'if [ -z "$dd_mode" ]; then',
            '    # Auto-detect: try GNU dd',
            '    if dd if=/dev/null of=/dev/null bs=1 count=0 iflag=skip_bytes 2>/dev/null; then',
            '        dd_mode="gnu"',
            '    else',
            '        dd_mode="plain"',
            '    fi',
            'fi',
            '',
            '# Helper functions',
            '# Generic copy function: copies bytes from a file/source at a given offset',
            '# Args: $1=source (file path), $2=skip_offset (bytes), $3=count (bytes), $4=source_type (file|script)',
            '_copy_generic() {',
            '    local source="$1"',
            '    local skip_offset=$2',
            '    local count=$3',
            '    local source_type=$4',
            '    local source_label="$5"  # for error messages',
            '    ',
            '    if [ "$dd_mode" = "gnu" ]; then',
            '        # GNU dd: use iflag for byte-level skip/count with large block size',
            '        [ "$verbose" -eq 1 ] && echo "dd if=\"$source\" bs=\"$block_size\" skip=\"$skip_offset\" count=$count iflag=skip_bytes,count_bytes" >&2',
            '        dd if="$source" bs="$block_size" skip="$skip_offset" count="$count" iflag=skip_bytes,count_bytes 2>/dev/null',
            '    elif [ "$dd_mode" = "plain" ]; then',
            '        # Plain dd: block-wise skip with count to restrict blocks, then head/tail for in-block precision',
            '        local skip_blocks=$(echo "$skip_offset / $block_size" | bc)',
            '        local skip_bytes=$(echo "$skip_offset % $block_size" | bc)',
            '        # Calculate how many blocks we need to read',
            '        local total_bytes_after_skip=$(echo "$skip_bytes + $count" | bc)',
            '        local blocks_to_read=$(echo "($total_bytes_after_skip + $block_size - 1) / $block_size" | bc)',
            '        ',
            '        # Optimize pipeline: omit tail if starting at block boundary (skip_bytes=0)',
            '        # and omit head if ending exactly at block boundary',
            '        local exact_multiple=$(echo "$blocks_to_read * $block_size" | bc)',
            '        local data_end=$(echo "$skip_bytes + $count" | bc)',
            '        local blocks_size=$(echo "$blocks_to_read * $block_size" | bc)',
            '        ',
            '        if [ "$skip_bytes" -eq 0 ] && [ "$count" = "$exact_multiple" ]; then',
            '            # No offset and count is exact multiple of block size: direct dd',
            '            [ "$verbose" -eq 1 ] && echo "dd if=\"$source\" bs=\"$block_size\" skip=$skip_blocks count=$blocks_to_read 2>/dev/null" >&2',
            '            dd if="$source" bs="$block_size" skip="$skip_blocks" count="$blocks_to_read" 2>/dev/null',
            '        elif [ "$skip_bytes" -eq 0 ]; then',
            '            # No offset, but count is not block-aligned: use head only',
            '            [ "$verbose" -eq 1 ] && echo "dd if=\"$source\" bs=\"$block_size\" skip=$skip_blocks count=$blocks_to_read 2>/dev/null | head -c $count" >&2',
            '            dd if="$source" bs="$block_size" skip="$skip_blocks" count="$blocks_to_read" 2>/dev/null | head -c "$count"',
            '        else',
            '            # Has offset: use tail and possibly head',
            '            local tail_pos=$(echo "$skip_bytes + 1" | bc)',
            '            if [ "$data_end" = "$blocks_size" ]; then',
            '                # Count goes to end of data read: tail only',
            '                [ "$verbose" -eq 1 ] && echo "dd if=\"$source\" bs=\"$block_size\" skip=$skip_blocks count=$blocks_to_read 2>/dev/null | tail -c +$tail_pos" >&2',
            '                dd if="$source" bs="$block_size" skip="$skip_blocks" count="$blocks_to_read" 2>/dev/null | tail -c +"$tail_pos"',
            '            else',
            '                # General case: need both tail and head',
            '                [ "$verbose" -eq 1 ] && echo "dd if=\"$source\" bs=\"$block_size\" skip=$skip_blocks count=$blocks_to_read 2>/dev/null | tail -c +$tail_pos | head -c $count" >&2',
            '                dd if="$source" bs="$block_size" skip="$skip_blocks" count="$blocks_to_read" 2>/dev/null | tail -c +"$tail_pos" | head -c "$count"',
            '            fi',
            '        fi',
            '    else',
            '        # No dd mode: pure tail/head (most portable)',
            '        local tail_offset=$(echo "$skip_offset + 1" | bc)',
            '        [ "$verbose" -eq 1 ] && echo "tail -c +$tail_offset \"$source\" | head -c $count" >&2',
            '        tail -c +"$tail_offset" "$source" | head -c "$count"',
            '    fi',
            '    ',
            '    if [ $? -ne 0 ]; then',
            '        echo "Error: Failed to copy $count bytes from $source_label at offset $skip_offset" >&2',
            '        exit 1',
            '    fi',
            '}',
            '',
            'copy_from_script() {',
            '    local skip_offset=$(echo "$data_offset + $1" | bc)',
            '    local count=$2',
            '    _copy_generic "$script_file" "$skip_offset" "$count" "script" "embedded data"',
            '}',
            '',
            'copy_from_file() {',
            '    local file="$1"',
            '    local skip=$2',
            '    local count=$3',
            '    _copy_generic "$file" "$skip" "$count" "file" "file $file"',
            '}',
            '',
        ])

        # If output file specified and tempfile requested, redirect to temp file for validation
        script_lines.extend([
            '# Setup output',
            'if [ -n "$output_file" ]; then',
            '    if [ "$use_tempfile" -eq 1 ]; then',
            '        temp_file="${output_file}.tmp.$$"',
            '        [ "$verbose" -eq 1 ] && echo "Using temporary file: $temp_file" >&2',
            '        exec > "$temp_file"',
            '    else',
            '        exec > "$output_file"',
            '    fi',
            'fi',
            '',
            '# Reconstruct the image',
            '[ "$verbose" -eq 1 ] && [ -n "$output_file" ] && echo "Reconstructing image..." >&2',
        ])

        # Add reconstruction commands
        for source, start_offset, end_offset in sequence:
            size = end_offset - start_offset
            if size == 0:
                continue

            if source == 'image':
                concat_offset = offset_mapping.map_offset(start_offset)
                script_lines.append(f'copy_from_script {concat_offset} {size}')
            else:
                escaped_path = escape_for_shell_display(str(source))
                script_lines.append(f"copy_from_file {escaped_path} {start_offset} {size}")

        script_lines.append('')

        # Validation and restoration (only if output file specified)
        script_lines.extend([
            '# Validate and restore metadata (only if output file specified)',
            'if [ -n "$output_file" ]; then',
            '    # Close stdout to finalize the file',
            '    exec >&-',
            '',
            '    # Determine target file for validation',
            '    if [ "$use_tempfile" -eq 1 ]; then',
            '        target_file="$temp_file"',
            '    else',
            '        target_file="$output_file"',
            '    fi',
            '',
            '    # Validate file size',
            f'    expected_size={image_info.size}',
            '    actual_size=$(wc -c < "$target_file")',
            '    if [ "$actual_size" -ne "$expected_size" ]; then',
            '        echo "Error: Size mismatch. Expected $expected_size bytes, got $actual_size bytes" >&2',
            '        exit_code=1',
            '    fi',
            '',
        ])

        # Add MD5 validation if available
        if image_info.md5:
            script_lines.extend([
                '    # Validate MD5 hash',
                '    if [ "$skip_md5" -eq 0 ]; then',
                '        [ "$verbose" -eq 1 ] && echo "Verifying MD5 hash..." >&2',
                '        if command -v md5sum >/dev/null 2>&1; then',
                '            actual_md5=$(md5sum "$target_file" | cut -d" " -f1)',
                '        elif command -v md5 >/dev/null 2>&1; then',
                '            # macOS md5 command',
                '            actual_md5=$(md5 -q "$target_file")',
                '        else',
                '            echo "Warning: md5sum/md5 not available, skipping MD5 verification" >&2',
                '            actual_md5=""',
                '        fi',
                '        if [ -n "$actual_md5" ]; then',
                '            if [ "$actual_md5" != "$file_md5" ]; then',
                '                echo "Error: MD5 mismatch. Expected $file_md5, got $actual_md5" >&2',
                '                exit_code=1',
                '            else',
                '                [ "$verbose" -eq 1 ] && echo "MD5 verification passed" >&2',
                '            fi',
                '        fi',
                '    fi',
                '',
            ])

        # Add SHA256 validation if available
        if image_info.sha256:
            script_lines.extend([
                '    # Validate SHA256 hash',
                '    if [ "$skip_sha256" -eq 0 ]; then',
                '        [ "$verbose" -eq 1 ] && echo "Verifying SHA256 hash..." >&2',
                '        if command -v sha256sum >/dev/null 2>&1; then',
                '            actual_sha256=$(sha256sum "$target_file" | cut -d" " -f1)',
                '        elif command -v shasum >/dev/null 2>&1; then',
                '            # macOS shasum command',
                '            actual_sha256=$(shasum -a 256 "$target_file" | cut -d" " -f1)',
                '        else',
                '            echo "Warning: sha256sum/shasum not available, skipping SHA256 verification" >&2',
                '            actual_sha256=""',
                '        fi',
                '        if [ -n "$actual_sha256" ]; then',
                '            if [ "$actual_sha256" != "$file_sha256" ]; then',
                '                echo "Error: SHA256 mismatch. Expected $file_sha256, got $actual_sha256" >&2',
                '                exit_code=1',
                '            else',
                '                [ "$verbose" -eq 1 ] && echo "SHA256 verification passed" >&2',
                '            fi',
                '        fi',
                '    fi',
                '',
            ])

        # Move temp file to final location (only if using tempfile)
        script_lines.extend([
            '    # Move temp file to final location (only if using tempfile)',
            '    if [ "$use_tempfile" -eq 1 ]; then',
            '        [ "$verbose" -eq 1 ] && echo "mv \"$temp_file\" \"$output_file\"" >&2',
            '        if ! mv "$temp_file" "$output_file"; then',
            '            echo "Error: Failed to move temporary file to $output_file" >&2',
            '            rm -f "$temp_file"',
            '            exit 1',
            '        fi',
            '    fi',
            '',
        ])

        # Restore permissions
        script_lines.extend([
            '    # Restore permissions',
            '    if [ "$skip_permissions" -eq 0 ]; then',
            '        [ "$verbose" -eq 1 ] && echo "chmod $file_perms \"$output_file\"" >&2',
            '        if ! chmod "$file_perms" "$output_file" 2>/dev/null; then',
            '            echo "Error: Failed to restore permissions" >&2',
            '            exit_code=1',
            '        fi',
            '    fi',
            '',
        ])

        # Restore ownership if available
        if image_info.owner and image_info.group:
            script_lines.extend([
                '    # Restore ownership',
                '    if [ "$skip_ownership" -eq 0 ]; then',
                '        if [ "$(id -u)" -eq 0 ]; then',
                '            [ "$verbose" -eq 1 ] && echo "chown $file_owner:$file_group \"$output_file\"" >&2',
                '            if ! chown "$file_owner:$file_group" "$output_file" 2>/dev/null; then',
                '                echo "Error: Failed to restore ownership" >&2',
                '                exit_code=1',
                '            fi',
                '        else',
                '            echo "Warning: Not running as root, cannot restore ownership" >&2',
                '        fi',
                '    fi',
                '',
            ])

        # Restore timestamps
        script_lines.extend([
            '    # Restore timestamps',
            '    if [ "$skip_timestamps" -eq 0 ]; then',
            '        [ "$verbose" -eq 1 ] && echo "touch -d \"@$file_mtime\" \"$output_file\"" >&2',
            '        # Try GNU touch -d format first (most portable modern approach)',
            '        if touch -d "@$file_mtime" "$output_file" 2>/dev/null; then',
            '            : # Success with GNU -d format',
            '        else',
            '            # Fallback: try to use BSD-style touch with date conversion',
            '            # On BSD systems, touch -t requires YYYYMMDDHHMM.SS format',
            '            # Note: date -r uses local time, not UTC, so we don\'t use -u flag',
            '            mtime_formatted=$(date -r "$file_mtime" +"%Y%m%d%H%M.%S" 2>/dev/null)',
            '            if [ -n "$mtime_formatted" ]; then',
            '                [ "$verbose" -eq 1 ] && echo "touch -t \"$mtime_formatted\" \"$output_file\"" >&2',
            '                if ! touch -t "$mtime_formatted" "$output_file" 2>/dev/null; then',
            '                    echo "Error: Failed to restore timestamps with BSD touch" >&2',
            '                    exit_code=1',
            '                fi',
            '            else',
            '                echo "Warning: Unable to restore timestamps (date conversion failed)" >&2',
            '            fi',
            '        fi',
            '    fi',
            '',
        ])

        # Restore ACL if available
        if image_info.acl:
            script_lines.extend([
                '    # Restore ACL',
                '    if [ "$skip_acl" -eq 0 ]; then',
                '        if command -v setfacl >/dev/null 2>&1; then',
                '            [ "$verbose" -eq 1 ] && echo "setfacl --restore=- \"$output_file\"" >&2',
                '            if ! echo "$file_acl" | setfacl --restore=- 2>/dev/null; then',
                '                echo "Error: Failed to restore ACL" >&2',
                '                exit_code=1',
                '            fi',
                '        else',
                '            echo "Warning: setfacl not available, skipping ACL restoration" >&2',
                '        fi',
                '    fi',
                '',
            ])

        script_lines.extend([
            '    if [ "$exit_code" -eq 0 ]; then',
            '        [ "$verbose" -eq 1 ] && echo "Successfully reconstructed: $output_file" >&2',
            '    else',
            '        echo "Reconstruction completed with errors: $output_file" >&2',
            '    fi',
            'fi',
            '',
            'exit $exit_code',
        ])

        return '\n'.join(script_lines) + '\n'


def generate_reconstruction_sequence(matches, image_size):
    """
    Generate a sequence of records to reconstruct the image file.

    Takes unsorted matches and produces a sequence of records that describes how to
    reconstruct the entire image. Each record specifies a source (either 'image' or
    a file path), start offset, and end offset. The sequence covers the entire image,
    preferring input files as sources whenever possible.

    Args:
        matches: List of tuples (file_path, file_start_byte, file_end_byte, image_start_byte, image_end_byte)
                 where each tuple represents a match between an input file and the image.
        image_size: Total size of the image in bytes.

    Returns:
        List of tuples (source, start_offset, end_offset) where:
        - source is either 'image' or a file path from the input files
        - start_offset is the starting byte position in the source
        - end_offset is the ending byte position in the source (exclusive)

    Example:
        If image is 1000 bytes and we have a match from bytes 100-200 in 'file.txt'
        that corresponds to bytes 300-400 in the image, the sequence would be:
        [('image', 0, 300), ('file.txt', 100, 200), ('image', 400, 1000)]
    """
    if not matches:
        # No matches - entire image needs to be used
        return [('image', 0, image_size)]

    # Sort by image_start_byte ascending, then by image_end_byte descending
    # This ensures we process matches in order of where they appear in the image,
    # and prefer longer matches when there are overlaps
    sorted_matches = sorted(matches, key=lambda m: (m[3], -m[4]))

    # Deduplicate overlapping matches
    deduplicated_matches = []
    last_end = 0  # Track the last end position in the image

    for file_path, file_start_byte, file_end_byte, image_start_byte, image_end_byte in sorted_matches:
        # If the last end is later than or equal to the end of this match, skip it
        if last_end >= image_end_byte:
            continue

        # Calculate the offset adjustment if there's overlap
        if last_end > image_start_byte:
            # There's partial overlap - adjust the start positions
            offset = last_end - image_start_byte
            adjusted_file_start = file_start_byte + offset
            adjusted_image_start = image_start_byte + offset
        else:
            # No overlap
            adjusted_file_start = file_start_byte
            adjusted_image_start = image_start_byte

        # Record this match (with adjusted positions if needed)
        deduplicated_matches.append((
            file_path,
            adjusted_file_start,
            file_end_byte,
            adjusted_image_start,
            image_end_byte
        ))

        # Update last_end to the end of this match
        last_end = image_end_byte

    # Now generate the reconstruction sequence
    # This includes both matched sections (from files) and unmatched sections (from image)
    reconstruction_sequence = []
    current_pos = 0

    for file_path, file_start_byte, file_end_byte, image_start_byte, image_end_byte in deduplicated_matches:
        # If there's a gap before this match, fill it with image data
        if current_pos < image_start_byte:
            reconstruction_sequence.append(('image', current_pos, image_start_byte))

        # Add the matched section from the file
        reconstruction_sequence.append((file_path, file_start_byte, file_end_byte))

        # Move current position to the end of this match
        current_pos = image_end_byte

    # If there's remaining image data after the last match, add it
    if current_pos < image_size:
        reconstruction_sequence.append(('image', current_pos, image_size))

    return reconstruction_sequence


def generate_shell_wrapper(script_text, attachment_ranges, attachment_file, output_stream, progress_callback=None, chunk_size=16*1024*1024):
    """
    Generate a self-extracting shell script wrapper.

    Takes a shell script and wraps it in a self-extracting format with embedded
    attachment data. The wrapper embeds the script directly and calculates proper
    offsets for extraction.

    Args:
        script_text: Shell script text (as string) to be embedded
        attachment_ranges: List of (start_offset, end_offset) tuples specifying which
                          ranges of the attachment file to include in the output
        attachment_file: Path to the attachment file to extract data from
        output_stream: Binary stream to write the complete shell script to (must support
                      binary write operations)
        progress_callback: Optional callable(bytes_written, total_bytes) for progress reporting
        chunk_size: Size of chunks in bytes for reading/writing attachment data (default: 16 MiB)

    The generated script structure:
    1. Header with embedded script and data offset variable
    2. Concatenated selected attachment data

    Example:
        script_text = "#!/bin/sh\\ndd if=file.bin bs=1 count=100\\n"
        attachment_ranges = [(0, 50), (200, 300)]
        generate_shell_wrapper(script_text, attachment_ranges, Path('img.bin'), output_file)
    """
    # Step 1: Create the complete wrapper script with embedded reconstruction script and placeholder
    # Placeholder will be a 20-digit number that we can replace later
    import textwrap

    placeholder = b'data_offset=00000000000000000000'

    # Encode each segment separately and concatenate as bytes in a single expression
    wrapper_script_bytes = (
        textwrap.dedent('''\
            #!/bin/sh
            set -e
            ''').encode('utf-8')
        + placeholder
        + textwrap.dedent('''\

            script_file="$0"

            # Embedded reconstruction script
            ''').encode('utf-8')
        + script_text.encode('utf-8')
        + textwrap.dedent('''\
            exit 0

            ''').encode('utf-8')
    )

    # Step 2: Calculate actual offset
    data_offset = len(wrapper_script_bytes)

    # Replace placeholder with actual offset in bytes
    # We need to keep the same byte length, so pad with spaces on the RIGHT
    # Format: 'data_offset=123                 ' (number followed by spaces to fill 20 chars)
    data_offset_bytes = str(data_offset).ljust(20).encode('ascii')

    # Replace in bytes - only replace the FIRST occurrence to avoid accidentally
    # replacing the same pattern if it appears in the embedded script
    replacement = b'data_offset=' + data_offset_bytes
    if placeholder not in wrapper_script_bytes:
        raise ValueError(f"Placeholder '{placeholder}' not found in wrapper script")
    wrapper_script_bytes = wrapper_script_bytes.replace(placeholder, replacement, 1)

    # Step 4: Output the complete script
    # Get the binary output buffer
    if hasattr(output_stream, 'buffer'):
        # Real file or stdout - use binary buffer
        output_buffer = output_stream.buffer
    else:
        # Already a binary stream
        output_buffer = output_stream

    # Write wrapper script (which contains the embedded reconstruction script)
    output_buffer.write(wrapper_script_bytes)

    # Calculate total bytes to write for progress reporting
    total_bytes = sum(end - start for start, end in attachment_ranges)
    bytes_written = 0

    # Write concatenated attachment data in chunks to handle large ranges
    with open(attachment_file, 'rb') as attach_f:
        for start_offset, end_offset in attachment_ranges:
            attach_f.seek(start_offset)
            remaining = end_offset - start_offset

            while remaining > 0:
                # Read and write in chunks
                to_read = min(chunk_size, remaining)
                data = attach_f.read(to_read)
                if not data:
                    raise IOError(f"Unexpected end of file at offset {attach_f.tell()}")

                output_buffer.write(data)
                bytes_written += len(data)
                remaining -= len(data)

                # Report progress if callback provided
                if progress_callback:
                    progress_callback(bytes_written, total_bytes)

    # Flush to ensure everything is written
    output_buffer.flush()


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

    parser.add_argument(
        '--no-ownership',
        action='store_true',
        help='Skip capturing ownership information (owner/group) for the image file'
    )

    parser.add_argument(
        '--no-acl',
        action='store_true',
        help='Skip capturing ACL (Access Control List) information for the image file'
    )

    parser.add_argument(
        '--no-md5',
        action='store_true',
        help='Skip calculating MD5 hash for the image file'
    )

    parser.add_argument(
        '--no-sha256',
        action='store_true',
        help='Skip calculating SHA256 hash for the image file'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose mode with timestamped progress messages to stderr'
    )

    parser.add_argument(
        '--write-chunk-size',
        type=int,
        default=16*1024*1024,
        metavar='BYTES',
        help='Chunk size in bytes for writing attachment data (default: 16777216, which is 16 MiB)'
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
    processor = ImageProcessor(
        args.image,
        args.output,
        block_size=args.block_size,
        min_extent_size=args.min_extent_size,
        capture_ownership=not args.no_ownership,
        capture_acl=not args.no_acl,
        capture_md5=not args.no_md5,
        capture_sha256=not args.no_sha256,
        verbose=args.verbose,
        write_chunk_size=args.write_chunk_size
    )

    try:
        # Process each file in the input list
        for file_path in read_file_list(args.input, args.null):
            processor.process_file(file_path)

        # Generate the reconstruction script
        processor.generate_script()

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
            # Make the output script executable
            os.chmod(args.output.name, 0o755)


if __name__ == '__main__':
    main()
