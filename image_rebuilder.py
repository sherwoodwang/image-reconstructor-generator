#!/usr/bin/env python3
"""
Image Rebuilder - Creates shell scripts to rebuild image files

This tool reads a list of files and generates a POSIX shell script that can
rebuild an image file from the extracted files.
"""

import argparse
import sys
from pathlib import Path


class ImageProcessor:
    """Processes files and generates shell script to rebuild an image."""

    def __init__(self, image_file: Path, output_stream=sys.stdout):
        """
        Initialize the image processor.

        Args:
            image_file: Path to the original image file
            output_stream: Stream to write the shell script to
        """
        self.image_file = image_file
        self.output_stream = output_stream

    def begin(self):
        """Start processing - write shell script header."""
        # TODO: Implement shell script header generation
        pass

    def process_file(self, file_path: str):
        """
        Process a single file from the input list.

        Args:
            file_path: Path to the file to process
        """
        # TODO: Implement file processing logic
        pass

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

    args = parser.parse_args()

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
    processor = ImageProcessor(args.image, args.output)

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
