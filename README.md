# Image Reconstructor Generator

## Overview

Image Reconstructor Generator is a tool that creates self-extracting shell scripts capable of reconstructing original image files from their extracted components. It analyzes extracted files, discovers reusable chunks that exist in the original image, and generates a standalone POSIX shell script that can reliably reconstruct the image with optional integrity verification and metadata restoration.

## Use Cases

- **Disk Image Backup & Recovery**: Reconstruct disk images from extracted file systems while preserving permissions, ownership, and timestamps
- **Archive Deduplication**: Generate efficient reconstruction scripts for tar files and other archives by reusing matching content from the original
- **Content Verification**: Create scripts that verify reconstructed files using MD5/SHA256 checksums
- **Cross-Platform Portability**: Generate scripts that work on any POSIX system (Linux, macOS, BSD) without requiring specialized tools
- **Forensic Analysis**: Reconstruct evidence files with full metadata preservation and integrity verification
- **Incremental Reconstruction**: Create scripts that can partially reconstruct images from a subset of extracted files

## How It Works

### The Reusable Extent Discovery Process

The tool operates in two phases:

**Phase 1: Analysis**
1. Computes block-level hashes (using MurmurHash3) for both the original image and extracted files
2. For each extracted file, scans through all positions looking for sequences of blocks that match the minimum extent size (default: 1 MiB). For each candidate match found via hash comparison, this identifies regions where the extracted file content appears to match a region in the original image
3. For each candidate match found via hash comparison, verifies the match at byte-level to eliminate false positives from hash collisions and confirm exact content alignment
4. Extends each verified match forward (toward the end of the file) to find the largest contiguous regions where the extracted file and image content are identical
5. Only keeps extents larger than the configured minimum size to reduce script complexity and avoid including trivial matches
6. When no match is found, the search position advances by the configured step size (default: same as minimum extent size). A smaller step size enables finding more extents but increases processing time

**Phase 2: Script Generation**
1. Creates a reconstruction sequence that specifies how to rebuild the image byte-for-byte
2. Embeds matched content from extracted files directly into the generated script
3. Includes fallback data from the original image for any unmatched regions
4. Generates a self-contained shell script with no external dependencies except standard POSIX tools

### Understanding Limitations

- **Block-Aligned Matching Only**: Content boundaries that don't align with block boundaries (default 4KB) cannot be matched as extents. This means small misalignments between extracted and original files will prevent matching, even if the content is identical.

- **Minimum Extent Size Filter**: The search process only considers matches that are at least the configured minimum size (default 1 MiB). Smaller matching regions, even if they exist and align with block boundaries, will not be reused. This keeps generated scripts manageable but means small files may be entirely included from the original image.

- **Step Size Impact on Extent Discovery**: The search process advances through files by the configured step size (default: same as minimum extent size) when no match is found. A coarser (larger) step size searches fewer positions and may miss valid extents that could have been discovered with finer-grained searching. For example, if the step size is 1 MiB, the tool skips ahead by entire megabytes when searching, potentially overlooking matching regions that lie between these skip points. Using a smaller step size enables discovering more extents but increases processing time proportionally. The trade-off is between discovery completeness and performance.

- **No Content-Aware Matching**: The tool cannot recognize logically equivalent content that has been reformatted or reorganized. Compressed archives, encrypted content, or files that have been modified (even in small ways) appear completely unmatched and must be included in full from the original image.

- **Script Size Growth**: The generated script size can grow significantly if few extents are discovered. Large images with little matching content will result in large scripts that embed most of the original image data.

## Setup

### Prerequisites for the Generator

- Python 3.8 or higher (required to run the generator tool itself)
- pip (Python package manager)

### Prerequisites for Generated Scripts

- POSIX-compatible shell (`sh`, `bash`, `zsh`, or similar) on the target system
- Standard POSIX utilities: `dd` or `tail`/`head` (depending on mode)
- `touch`, `chmod`, `chown` (for metadata restoration)
- Optional: `md5sum`/`md5`, `sha256sum`/`shasum` (for checksum verification)

### Installation

1. Clone or download the project
2. Create a virtual environment:
```bash
python3 -m venv venv
```

3. Activate the virtual environment:
```bash
source venv/bin/activate
```

4. Install the project in editable mode with dependencies:
```bash
pip install -e .
```

### Dependencies

The project uses:
- `mmh3>=4.0.0` - MurmurHash3 implementation for fast block-level hashing

## Usage

### Quick Start

```bash
# Generate a reconstruction script from extracted files
find extracted_dir -type f | ./image_reconstructor_generator.py original.img > reconstruct.sh

# Run the reconstruction script
chmod +x reconstruct.sh
./reconstruct.sh output.img
```

### Command-Line Interface

```bash
image-reconstructor-generator <image> [options]

Positional Arguments:
  image                         Path to the original image file

Input Options:
  -i, --input FILE              Read file list from FILE instead of stdin
  -0, --null                    File list is null-separated (like find -print0)

Output Options:
  -o, --output FILE             Write shell script to FILE instead of stdout

Analysis Options:
  -b, --block-size BYTES        Block size for hashing (default: 4096)
  -m, --min-extent-size BYTES   Minimum reusable extent size (default: 1048576)
  -s, --step-size BYTES         Step size for searching when no match found (default: same as min-extent-size)

Metadata Options:
  --no-ownership                Skip capturing file ownership information
  --no-acl                      Skip capturing ACL information
  --no-md5                      Skip calculating MD5 hash
  --no-sha256                   Skip calculating SHA256 hash

Other Options:
  -v, --verbose                 Show timestamped progress messages
  --write-chunk-size BYTES      Chunk size for output writing (default: 16777216)
  -h, --help                    Show this help message
```

### Examples

**Basic usage with stdin (newline-separated):**
```bash
find extracted_dir -type f | image-reconstructor-generator original.img > reconstruct.sh
```

**With null-separated input (handles special characters):**
```bash
find extracted_dir -type f -print0 | image-reconstructor-generator -0 original.img > reconstruct.sh
```

**From a saved file list:**
```bash
image-reconstructor-generator original.img -i files.txt > reconstruct.sh
```

**Write to a file directly:**
```bash
image-reconstructor-generator original.img -i files.txt -o reconstruct.sh
chmod +x reconstruct.sh
```

**With larger block size for faster analysis:**
```bash
image-reconstructor-generator -b 8192 original.img -i files.txt > reconstruct.sh
```

**With custom step size for finer-grained search:**
```bash
image-reconstructor-generator -s 262144 original.img -i files.txt > reconstruct.sh
```

**Verbose output to monitor progress:**
```bash
image-reconstructor-generator -v original.img -i files.txt > reconstruct.sh 2> progress.log
```

### Generated Script Usage

Once you have a reconstruction script, run it with:

```bash
# Show image information without reconstructing
./reconstruct.sh -i

# Reconstruct to a file with verification
./reconstruct.sh output.img

# Reconstruct to stdout
./reconstruct.sh > output.img

# Skip checksum verification (faster)
./reconstruct.sh -M -S output.img

# Use portable mode (no GNU dd, just POSIX tools)
./reconstruct.sh -x no-dd output.img

# Overwrite existing file
./reconstruct.sh -x overwrite output.img

# Verbose reconstruction
./reconstruct.sh -v output.img
```

**Generated Script Options:**
- `-i`: Show image information only (don't reconstruct)
- `-M`: Skip MD5 verification
- `-S`: Skip SHA256 verification
- `-p`: Skip permission restoration
- `-o`: Skip ownership restoration
- `-t`: Skip timestamp restoration
- `-a`: Skip ACL restoration
- `-T`: Use intermediate temporary file for validation
- `-v`: Verbose mode (show progress messages)
- `-b SIZE`: Block size for dd operations
- `-x OPTS`: Extra options (gnu-dd, plain-dd, no-dd, allow-tty, overwrite)
- `-h`: Show help message

## Development

### Running Tests

Ensure the virtual environment is activated:

```bash
source venv/bin/activate
```

**Run all tests:**
```bash
python3 -m unittest discover tests -v
```

**Run specific test module:**
```bash
python3 -m unittest tests.test_image_reconstructor_generator -v
```

**Run with minimal output:**
```bash
python3 -m unittest discover tests
```

### Type Checking

This project uses [pyright](https://github.com/microsoft/pyright) for static type checking.

**Install pyright:**
```bash
source venv/bin/activate
pip install pyright
```

**Run type checking:**
```bash
pyright image_reconstructor_generator.py
```

All code must pass type checking with 0 errors before committing.

### Validation Steps Before Committing

1. **Run tests** - Ensure all tests pass:
   ```bash
   python3 -m unittest discover tests -v
   ```

2. **Type check** - Verify no type errors:
   ```bash
   pyright image_reconstructor_generator.py
   ```

3. **Test script generation** - Create a test script:
   ```bash
   find test_files -type f | python3 image_reconstructor_generator.py test_image.bin > test_reconstruct.sh
   chmod +x test_reconstruct.sh
   ```

4. **Verify reconstruction** - Test the generated script works:
   ```bash
   ./test_reconstruct.sh -i  # Show image info
   ./test_reconstruct.sh test_output.bin  # Reconstruct
   cmp test_image.bin test_output.bin  # Verify byte-for-byte match
   ```

