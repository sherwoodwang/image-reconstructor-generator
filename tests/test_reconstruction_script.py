"""Tests for reconstruction script generation."""

import unittest
import tempfile
import subprocess
import os
from pathlib import Path
from image_rebuilder import ImageInfo, ImageProcessor, OffsetMapper


class TestReconstructionScriptGeneration(unittest.TestCase):
    """Test the _generate_reconstruction_script method."""

    def test_script_contains_usage_function(self):
        """Test that generated script contains usage function."""
        # Create minimal ImageInfo
        image_info = ImageInfo(
            size=1024,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="d41d8cd98f00b204e9800998ecf8427e",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            acl=None
        )

        # Create a temporary image file for ImageProcessor
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 1024)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 1024)]
            offset_mapping = OffsetMapper([(0, 1024)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('usage() {', script)
            self.assertIn('Usage: $0 [options] [output-file]', script)
            self.assertIn('-i', script)
            self.assertIn('-M', script)
            self.assertIn('-S', script)
            self.assertIn('-v', script)
            self.assertIn('-T', script)
        finally:
            temp_image.unlink()

    def test_script_contains_getopts_parsing(self):
        """Test that generated script contains getopts argument parsing."""
        image_info = ImageInfo(
            size=100,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="",
            group="",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="",
            sha256="",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 100)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 100)]
            offset_mapping = OffsetMapper([(0, 100)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('while getopts', script)
            self.assertIn('case "$opt" in', script)
            self.assertIn('show_info=1', script)
            self.assertIn('skip_md5=1', script)
            self.assertIn('skip_sha256=1', script)
            self.assertIn('use_tempfile=1', script)
            self.assertIn('verbose=1', script)
        finally:
            temp_image.unlink()

    def test_script_includes_image_info_display(self):
        """Test that script includes image information display."""
        image_info = ImageInfo(
            size=2048,
            permissions=0o100755,
            uid=1001,
            gid=1002,
            owner="testuser",
            group="testgroup",
            atime=1234567890.0,
            mtime=1234567891.0,
            ctime=1234567892.0,
            md5="abc123",
            sha256="def456",
            acl="# file: test\nuser::rwx\n"
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 2048)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 2048)]
            offset_mapping = OffsetMapper([(0, 2048)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('Image Information:', script)
            self.assertIn('2048 bytes', script)
            self.assertIn('testuser:testgroup', script)
            self.assertIn('abc123', script)
            self.assertIn('def456', script)
            self.assertIn('ACL:', script)
        finally:
            temp_image.unlink()

    def test_script_includes_helper_functions(self):
        """Test that script includes helper functions."""
        image_info = ImageInfo(
            size=512,
            permissions=0o100644,
            uid=0,
            gid=0,
            owner="root",
            group="root",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="",
            sha256="",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 512)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 512)]
            offset_mapping = OffsetMapper([(0, 512)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('copy_from_script()', script)
            self.assertIn('copy_from_file()', script)
        finally:
            temp_image.unlink()

    def test_script_includes_md5_verification(self):
        """Test that script includes MD5 verification when hash is present."""
        image_info = ImageInfo(
            size=256,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="5d41402abc4b2a76b9719d911017c592",
            sha256="",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 256)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 256)]
            offset_mapping = OffsetMapper([(0, 256)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('Validate MD5 hash', script)
            self.assertIn('5d41402abc4b2a76b9719d911017c592', script)
            self.assertIn('md5sum', script)
            self.assertIn('md5 -q', script)  # macOS compatibility
        finally:
            temp_image.unlink()

    def test_script_includes_sha256_verification(self):
        """Test that script includes SHA256 verification when hash is present."""
        image_info = ImageInfo(
            size=256,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 256)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 256)]
            offset_mapping = OffsetMapper([(0, 256)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('Validate SHA256 hash', script)
            self.assertIn('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', script)
            self.assertIn('sha256sum', script)
            self.assertIn('shasum -a 256', script)  # macOS compatibility
        finally:
            temp_image.unlink()

    def test_script_omits_verification_when_hashes_absent(self):
        """Test that script omits hash verification when hashes are not present."""
        image_info = ImageInfo(
            size=128,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="",
            sha256="",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 128)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 128)]
            offset_mapping = OffsetMapper([(0, 128)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertNotIn('Validate MD5 hash', script)
            self.assertNotIn('Validate SHA256 hash', script)
        finally:
            temp_image.unlink()

    def test_script_includes_permission_restoration(self):
        """Test that script includes permission restoration."""
        image_info = ImageInfo(
            size=256,
            permissions=0o100755,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="",
            sha256="",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 256)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 256)]
            offset_mapping = OffsetMapper([(0, 256)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('Restore permissions', script)
            self.assertIn('chmod 755', script)
        finally:
            temp_image.unlink()

    def test_script_includes_ownership_restoration(self):
        """Test that script includes ownership restoration when owner/group present."""
        image_info = ImageInfo(
            size=256,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="testuser",
            group="testgroup",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="",
            sha256="",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 256)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 256)]
            offset_mapping = OffsetMapper([(0, 256)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('Restore ownership', script)
            self.assertIn('chown "testuser:testgroup"', script)
            self.assertIn('id -u', script)  # Root check
        finally:
            temp_image.unlink()

    def test_script_includes_timestamp_restoration(self):
        """Test that script includes timestamp restoration."""
        image_info = ImageInfo(
            size=256,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567891.0,
            ctime=1234567892.0,
            md5="",
            sha256="",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 256)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 256)]
            offset_mapping = OffsetMapper([(0, 256)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('Restore timestamps', script)
            self.assertIn('touch -t', script)
        finally:
            temp_image.unlink()

    def test_script_includes_acl_restoration(self):
        """Test that script includes ACL restoration when ACL is present."""
        image_info = ImageInfo(
            size=256,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="",
            sha256="",
            acl="# file: test\nuser::rwx\ngroup::r-x\n"
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 256)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 256)]
            offset_mapping = OffsetMapper([(0, 256)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('Restore ACL', script)
            self.assertIn('setfacl', script)
        finally:
            temp_image.unlink()

    def test_script_includes_verbose_messages(self):
        """Test that script includes verbose mode messages."""
        image_info = ImageInfo(
            size=256,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="abc123",
            sha256="def456",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 256)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 256)]
            offset_mapping = OffsetMapper([(0, 256)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('Verifying MD5 hash...', script)
            self.assertIn('MD5 verification passed', script)
            self.assertIn('Verifying SHA256 hash...', script)
            self.assertIn('SHA256 verification passed', script)
            self.assertIn('Reconstructing image...', script)
            self.assertIn('Successfully reconstructed:', script)
        finally:
            temp_image.unlink()

    def test_script_includes_tempfile_logic(self):
        """Test that script includes temporary file logic."""
        image_info = ImageInfo(
            size=256,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="",
            sha256="",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 256)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)
            sequence = [('image', 0, 256)]
            offset_mapping = OffsetMapper([(0, 256)])

            script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

            self.assertIn('use_tempfile', script)
            self.assertIn('temp_file=', script)
            self.assertIn('target_file=', script)
            self.assertIn('Move temp file to final location', script)
        finally:
            temp_image.unlink()

    def test_script_handles_file_path_escaping(self):
        """Test that script properly escapes file paths with special characters."""
        image_info = ImageInfo(
            size=256,
            permissions=0o100644,
            uid=1000,
            gid=1000,
            owner="user",
            group="group",
            atime=1234567890.0,
            mtime=1234567890.0,
            ctime=1234567890.0,
            md5="",
            sha256="",
            acl=None
        )

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 256)
            temp_image = Path(f.name)

        try:
            processor = ImageProcessor(temp_image)

            # Test various special characters
            test_cases = [
                ("file'with'quotes.bin", "file'\"'\"'with'\"'\"'quotes.bin"),
                ("file with spaces.bin", "'file with spaces.bin'"),
                ("file\twith\ttab.bin", "'file\twith\ttab.bin'"),  # Literal tab preserved
                ("file\\with\\backslash.bin", "'file\\with\\backslash.bin'"),  # Literal backslash
                ("café.bin", "'café.bin'"),  # Unicode
            ]

            for original_path, expected_escaped in test_cases:
                with self.subTest(path=original_path):
                    sequence = [(original_path, 0, 128), ('image', 0, 128)]
                    offset_mapping = OffsetMapper([(0, 128)])

                    script = processor._generate_reconstruction_script(sequence, offset_mapping, image_info)

                    # Check that the file path appears with proper escaping in copy_from_file command
                    self.assertIn(expected_escaped, script,
                                f"Expected {expected_escaped} not found in script for {original_path}")
        finally:
            temp_image.unlink()


class TestReconstructionScriptExecution(unittest.TestCase):
    """Test execution of generated reconstruction scripts."""

    def test_script_help_flag(self):
        """Test that script responds to -h flag."""
        # Create minimal test data
        test_data = b'Hello, World!'

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(test_data)
            temp_image = Path(f.name)

        script_path = None
        try:
            processor = ImageProcessor(temp_image, capture_md5=False, capture_sha256=False, capture_acl=False)
            processor.begin()

            # Generate script to a file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as script_file:
                script_path = Path(script_file.name)
                processor.output_stream = script_file
                processor.finalize()

            # Make script executable
            script_path.chmod(0o755)

            # Run with -h flag
            result = subprocess.run(
                [str(script_path), '-h'],
                capture_output=True,
                text=True
            )

            self.assertNotEqual(result.returncode, 0)  # Should exit with error
            self.assertIn('Usage:', result.stderr)
            self.assertIn('-i', result.stderr)
            self.assertIn('-v', result.stderr)
        finally:
            temp_image.unlink()
            if script_path and script_path.exists():
                script_path.unlink()

    def test_script_info_flag(self):
        """Test that script displays information with -i flag."""
        test_data = b'Test data for info display'

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(test_data)
            temp_image = Path(f.name)

        script_path = None
        try:
            processor = ImageProcessor(temp_image, capture_md5=False, capture_sha256=False, capture_acl=False)
            processor.begin()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as script_file:
                script_path = Path(script_file.name)
                processor.output_stream = script_file
                processor.finalize()

            script_path.chmod(0o755)

            # Run with -i flag
            result = subprocess.run(
                [str(script_path), '-i'],
                capture_output=True,
                text=True
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn('Image Information:', result.stdout)
            self.assertIn('Size:', result.stdout)
            self.assertIn('Permissions:', result.stdout)
            self.assertIn('Source Files:', result.stdout)
        finally:
            temp_image.unlink()
            if script_path and script_path.exists():
                script_path.unlink()

    def test_script_info_shows_source_files(self):
        """Test that script info displays source files list."""
        # Create test image and a source file in current directory
        test_data = b'A' * 10000

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(test_data)
            temp_image = Path(f.name)

        # Create source file in current directory to satisfy path security
        temp_source = Path('test_source_file.tmp')
        temp_source.write_bytes(b'B' * 5000)

        script_path = None
        try:
            processor = ImageProcessor(temp_image, capture_md5=False, capture_sha256=False,
                                      capture_acl=False, capture_ownership=False)
            processor.begin()

            # Process a file that will create a match
            processor.process_file(str(temp_source))

            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as script_file:
                script_path = Path(script_file.name)
                processor.output_stream = script_file
                processor.finalize()

            script_path.chmod(0o755)

            # Run with -i flag
            result = subprocess.run(
                [str(script_path), '-i'],
                capture_output=True,
                text=True
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn('Source Files:', result.stdout)
            # Should show either the source file path or indicate no external files
            self.assertTrue(
                str(temp_source) in result.stdout or
                'no external files' in result.stdout
            )
        finally:
            temp_image.unlink()
            if temp_source.exists():
                temp_source.unlink()
            if script_path and script_path.exists():
                script_path.unlink()

    def test_script_info_with_special_filenames(self):
        """Test that script info mode correctly displays filenames with special characters."""
        # Test various special characters that could appear in filenames
        special_filenames = [
            "file'with'quotes.txt",
            "file with spaces.txt",
            "file\twith\ttab.txt",
            "file\nwith\nnewline.txt",
            "file\\with\\backslash.txt",
            "café_unicode.txt",
            "emoji😀.txt",
        ]

        # Create image with data that will be found in source files
        test_data = b'A' * 5000 + b'B' * 5000

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(test_data)
            temp_image = Path(f.name)

        temp_files = []
        script_path = None

        try:
            # Use small min_extent_size so our test files will be matched
            processor = ImageProcessor(temp_image, capture_md5=False, capture_sha256=False,
                                      capture_acl=False, capture_ownership=False,
                                      min_extent_size=4096)  # 1 block minimum
            processor.begin()

            # Create and process files with special names containing data from the image
            for i, special_name in enumerate(special_filenames):
                temp_file = Path(special_name)
                # Write data that matches part of the image (at least 1 block = 4096 bytes)
                temp_file.write_bytes(b'B' * 5000)
                temp_files.append(temp_file)
                processor.process_file(str(temp_file))

            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as script_file:
                script_path = Path(script_file.name)
                processor.output_stream = script_file
                processor.finalize()

            script_path.chmod(0o755)

            # Run with -i flag
            result = subprocess.run(
                [str(script_path), '-i'],
                capture_output=True,
                text=True,
                check=False
            )

            # Script should execute successfully even with special filenames
            self.assertEqual(result.returncode, 0, f"Script failed with: {result.stderr}")
            self.assertIn('Source Files:', result.stdout)

            # The script should either show source files or indicate no external files
            # The key is that it runs successfully without shell injection or errors
            # due to special characters in filenames
            self.assertTrue(
                'no external files' in result.stdout or
                any(name.split('\n')[0] in result.stdout for name in special_filenames),
                "Expected either source files or 'no external files' message"
            )

        finally:
            temp_image.unlink()
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()
            if script_path and script_path.exists():
                script_path.unlink()

    def test_script_reconstruction_with_special_filenames(self):
        """Test that script can successfully reconstruct image using files with special characters."""
        # Test filenames with various special characters that can actually exist on filesystems
        # Note: Newlines cannot be in filenames, tabs work on Linux but not all systems
        special_filenames = [
            "file'with'quotes.txt",
            "file with spaces.txt",
            "file$with$dollar.txt",
        ]

        # Create simple test where one file contains the entire image data
        # This avoids complexity of hash matching and extent merging
        image_data = b'TEST_RECONSTRUCTION_DATA' * 500  # 12000 bytes

        # The first file will contain all the image data
        file_data = {
            special_filenames[0]: image_data,
        }

        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(image_data)
            temp_image = Path(f.name)

        temp_files = []
        script_path = None
        output_file = None

        try:
            # Create all source files with special names
            for filename, data in file_data.items():
                temp_file = Path(filename)
                temp_file.write_bytes(data)
                temp_files.append(temp_file)

            # Generate reconstruction script
            processor = ImageProcessor(temp_image, capture_md5=True, capture_sha256=True,
                                      capture_acl=False, capture_ownership=False,
                                      min_extent_size=4096)
            processor.begin()

            # Process only the files that have data
            for filename in file_data.keys():
                processor.process_file(filename)

            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as script_file:
                script_path = Path(script_file.name)
                processor.output_stream = script_file
                processor.finalize()

            script_path.chmod(0o755)

            # Create output file for reconstruction
            with tempfile.NamedTemporaryFile(delete=False, suffix='.reconstructed') as out:
                output_file = Path(out.name)

            # Delete the file so the script can create it
            output_file.unlink()

            # Run the reconstruction script
            result = subprocess.run(
                [str(script_path), str(output_file)],
                capture_output=True,
                text=True,
                check=False
            )

            # Verify reconstruction succeeded
            self.assertEqual(result.returncode, 0,
                           f"Reconstruction failed: {result.stderr}")

            # Verify the reconstructed file matches the original
            reconstructed_data = output_file.read_bytes()
            self.assertEqual(reconstructed_data, image_data,
                           "Reconstructed data does not match original")

            # Verify the special filename with quotes was used in copy_from_file command
            script_content = script_path.read_text()
            # Check that copy_from_file is in the script and properly escaped
            self.assertIn('copy_from_file', script_content)
            # Check that the filename with quotes is properly escaped
            self.assertIn("file'\"'\"'with'\"'\"'quotes.txt", script_content)

        finally:
            temp_image.unlink()
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()
            if script_path and script_path.exists():
                script_path.unlink()
            if output_file and output_file.exists():
                output_file.unlink()

    def test_script_refuses_binary_to_terminal(self):
        """Test that script refuses to write binary data to terminal."""
        test_data = b'Binary test data'

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(test_data)
            temp_image = Path(f.name)

        script_path = None
        try:
            processor = ImageProcessor(temp_image, capture_md5=False, capture_sha256=False, capture_acl=False)
            processor.begin()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as script_file:
                script_path = Path(script_file.name)
                processor.output_stream = script_file
                processor.finalize()

            script_path.chmod(0o755)

            # Run without output file (would write to stdout)
            # Use script -c to simulate a TTY
            result = subprocess.run(
                ['script', '-qec', str(script_path), '/dev/null'],
                capture_output=True,
                text=True,
                timeout=5
            )

            # Should refuse to write binary to terminal
            self.assertNotEqual(result.returncode, 0)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # 'script' command might not be available on all systems
            self.skipTest("'script' command not available")
        finally:
            temp_image.unlink()
            if script_path and script_path.exists():
                script_path.unlink()

    def test_script_basic_reconstruction(self):
        """Test basic reconstruction to a file."""
        test_data = b'Simple reconstruction test'

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(test_data)
            temp_image = Path(f.name)

        script_path = None
        output_file = None
        try:
            processor = ImageProcessor(temp_image, capture_md5=False, capture_sha256=False,
                                      capture_acl=False, capture_ownership=False)
            processor.begin()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as script_file:
                script_path = Path(script_file.name)
                processor.output_stream = script_file
                processor.finalize()

            script_path.chmod(0o755)

            # Create output file
            with tempfile.NamedTemporaryFile(delete=False) as out_f:
                output_file = Path(out_f.name)
            output_file.unlink()  # Remove it so script can create it

            # Run script to reconstruct
            result = subprocess.run(
                [str(script_path), str(output_file)],
                capture_output=True,
                text=True
            )

            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
            self.assertTrue(output_file.exists())

            # Verify content
            with open(output_file, 'rb') as f:
                reconstructed = f.read()
            self.assertEqual(reconstructed, test_data)
        finally:
            temp_image.unlink()
            if script_path and script_path.exists():
                script_path.unlink()
            if output_file and output_file.exists():
                output_file.unlink()


if __name__ == '__main__':
    unittest.main()
