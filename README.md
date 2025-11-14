# Image Rebuilder

The program provided by this project is intended to be used to create a shell script that can be executed with POSIX shell to rebuild an image file (e.g., a disk image, a tarball, etc.) from a set of files that are extracted from that image.

## Setup

### Prerequisites

- Python 3.8 or higher

### Installation

1. Create a virtual environment:
```bash
python3 -m venv venv
```

2. Activate the virtual environment:
```bash
source venv/bin/activate
```

3. Install the project in editable mode with dependencies:
```bash
pip install -e .
```

### Dependencies

The project uses the following dependencies (managed via `pyproject.toml`):
- `mmh3>=4.0.0` - MurmurHash3 implementation for efficient hashing

## Usage

```bash
# Basic usage with stdin (newline-separated)
find extracted_dir -type f | ./image_rebuilder.py original.img > rebuild.sh

# With null-separated input (handles special characters in filenames)
find extracted_dir -type f -print0 | ./image_rebuilder.py -0 original.img > rebuild.sh

# From a saved file list
./image_rebuilder.py original.img -i files.txt > rebuild.sh

# Write output to a file
./image_rebuilder.py original.img -i files.txt -o rebuild.sh
```

### Options

- `image`: Path to the original image file (required)
- `-i, --input FILE`: Read file list from FILE instead of stdin
- `-0, --null`: File list is null-separated (like `find -print0`) instead of newline-separated
- `-o, --output FILE`: Write shell script to FILE instead of stdout

## Development

### Running Tests

Make sure you have activated the virtual environment first:

```bash
source venv/bin/activate
```

Run the test suite using Python's unittest:

```bash
python3 -m unittest tests.test_image_rebuilder -v
```

Or run all tests in the tests directory:

```bash
python3 -m unittest discover tests -v
```

For quieter output (just pass/fail):

```bash
python3 -m unittest tests.test_image_rebuilder
```

### Test Coverage

The test suite includes:
- File list reading (newline and null-separated)
- Argument parsing
- ImageProcessor class functionality
- Error handling
- End-to-end integration tests
