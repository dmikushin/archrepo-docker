#!/usr/bin/env python3
"""
test_archrepo_api.py - Test harness for ArchRepo API

This script sets up a direct connection between archrepo.api and pkg-shell.sh
without using SSH/network connections, allowing for efficient testing inside
a Docker container.
"""

import os
import sys
import base64
import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import archrepo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from archrepo.api import ArchRepoClient


class MockShellProcess:
    """Simulates the interactive shell process without requiring SSH"""

    def __init__(self, pkg_shell_path):
        self.pkg_shell_path = pkg_shell_path
        self.returncode = 0
        self.stdout = ""
        self.stderr = ""

    def communicate(self, input=None):
        """Directly process commands that would normally go through SSH"""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_input:
            temp_input.write(input)
            temp_input.flush()

            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_output:
                # Run the pkg-shell script with the commands
                cmd = [
                    'bash',
                    self.pkg_shell_path,
                    # You may need to add arguments here to set up repo paths
                    # Or modify pkg-shell.sh to accept different paths for testing
                ]

                # Set environment variables for testing
                env = os.environ.copy()
                env['REPO_DIR'] = '/tmp/test_repo/x86_64'
                env['DB_NAME'] = 'repo.db.tar.gz'
                env['TESTING'] = '1'

                proc = subprocess.run(
                    cmd,
                    env=env,
                    input=input,
                    text=True,
                    capture_output=True
                )

                self.returncode = proc.returncode
                self.stdout = proc.stdout
                self.stderr = proc.stderr

                return self.stdout, self.stderr


class TestArchRepoAPI(unittest.TestCase):
    """Test suite for the ArchRepo API"""

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests"""
        # Create test repository directory
        cls.test_dir = Path('/tmp/test_repo')
        cls.x86_64_dir = cls.test_dir / 'x86_64'
        cls.x86_64_dir.mkdir(parents=True, exist_ok=True)

        # Create test uploads directory
        cls.uploads_dir = Path('/tmp/uploads')
        cls.uploads_dir.mkdir(parents=True, exist_ok=True)

        # Path to pkg-shell.sh - adjust as needed
        cls.pkg_shell_path = Path(__file__).parent.parent.parent / 'pkg-shell.sh'

        # Create a dummy package file
        cls.dummy_pkg_path = cls._create_dummy_package()

        # Initialize repo database
        subprocess.run(['repo-add', str(cls.x86_64_dir / 'repo.db.tar.gz')],
                      check=True)

    @classmethod
    def _create_dummy_package(cls):
        """Create a dummy .pkg.tar.zst file and its signature for testing"""
        # Create a dummy file with some content
        pkg_path = cls.test_dir / 'testpackage-1.0-1-x86_64.pkg.tar.zst'

        # Create a simple tarball as our dummy package
        subprocess.run([
            'tar', 'czf', str(pkg_path),
            '-C', '/', 'etc/passwd'  # Just include a system file
        ], check=True)

        # Create a dummy signature file
        sig_path = Path(f"{pkg_path}.sig")
        with open(sig_path, 'wb') as f:
            f.write(b'DUMMY SIGNATURE')

        return pkg_path

    def setUp(self):
        """Set up before each test method"""
        # Create a client for testing
        self.client = ArchRepoClient(host="dummy")  # Host won't be used

        # Mock the _run_ssh_interactive method to use our direct connection
        self.orig_run_ssh = self.client._run_ssh_interactive

        def mock_run_ssh(commands):
            """Mock the SSH connection with direct process interaction"""
            mock_process = MockShellProcess(self.pkg_shell_path)

            # Prepare the complete input just like the original method
            input_data = "\n".join(commands + ["exit"]) + "\n"

            stdout, stderr = mock_process.communicate(input=input_data)
            return mock_process.returncode, stdout, stderr

        self.client._run_ssh_interactive = mock_run_ssh

    def tearDown(self):
        """Clean up after each test method"""
        # Restore original method
        self.client._run_ssh_interactive = self.orig_run_ssh

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are done"""
        # Clean up test files
        import shutil
        shutil.rmtree(cls.test_dir, ignore_errors=True)
        shutil.rmtree(cls.uploads_dir, ignore_errors=True)

    def test_publish_package(self):
        """Test publishing a package to the repository"""
        success, message = self.client.publish_package(str(self.dummy_pkg_path))
        self.assertTrue(success)
        self.assertIn("Package", message)

        # Verify package was added to repo
        self.assertTrue((self.x86_64_dir / Path(self.dummy_pkg_path).name).exists())

    def test_list_packages(self):
        """Test listing packages in the repository"""
        # First publish a package
        self.client.publish_package(str(self.dummy_pkg_path))

        # Then list packages
        success, packages = self.client.list_packages()
        self.assertTrue(success)
        self.assertTrue(isinstance(packages, list))
        self.assertGreaterEqual(len(packages), 1)

        # Verify our package is in the list
        pkg_names = [pkg['name'] for pkg in packages]
        self.assertIn('testpackage', pkg_names)

    def test_remove_package(self):
        """Test removing a package from the repository"""
        # First publish a package
        self.client.publish_package(str(self.dummy_pkg_path))

        # Then remove it
        success, message = self.client.remove_package("testpackage")
        self.assertTrue(success)
        self.assertIn("removed", message.lower())

        # Verify package was removed
        success, packages = self.client.list_packages()
        pkg_names = [pkg['name'] for pkg in packages]
        self.assertNotIn('testpackage', pkg_names)

    def test_clean_repository(self):
        """Test cleaning the repository"""
        # Add multiple versions of a package
        for version in ['1.0', '1.1', '1.2']:
            pkg_path = self.test_dir / f'testpackage-{version}-1-x86_64.pkg.tar.zst'

            # Create a dummy package
            with open(pkg_path, 'wb') as f:
                f.write(f'DUMMY PACKAGE {version}'.encode())

            # Create a dummy signature
            with open(f'{pkg_path}.sig', 'wb') as f:
                f.write(f'DUMMY SIGNATURE {version}'.encode())

            # Publish it
            self.client.publish_package(str(pkg_path))

        # Clean the repository
        success, message = self.client.clean_repository()
        self.assertTrue(success)
        self.assertIn("cleaned", message.lower())

        # Verify only one version remains
        files = list(self.x86_64_dir.glob('testpackage-*.pkg.tar.zst'))
        self.assertEqual(len(files), 1)
        self.assertTrue(str(files[0]).endswith('1.2-1-x86_64.pkg.tar.zst'))

    def test_get_status(self):
        """Test getting repository status"""
        # First publish a package
        self.client.publish_package(str(self.dummy_pkg_path))

        # Get status
        success, status = self.client.get_status()
        self.assertTrue(success)
        self.assertIsInstance(status, dict)
        self.assertIn('Total packages', status)
        self.assertGreaterEqual(int(status.get('Total packages', '0')), 1)


def create_docker_test_script():
    """Create a script to run tests inside a Docker container"""
    script_content = """#!/bin/bash
# Run ArchRepo API tests in Docker

set -e

# Install necessary packages
pacman -Sy --noconfirm base-devel git python python-pip

# Install Python dependencies for testing
pip install pytest

# Set up repository directories
mkdir -p /tmp/test_repo/x86_64
mkdir -p /tmp/uploads

# Run the tests
cd /path/to/tests
python -m unittest test_archrepo_api.py
"""

    script_path = Path(__file__).parent / 'run_tests_in_docker.sh'
    with open(script_path, 'w') as f:
        f.write(script_content)

    os.chmod(script_path, 0o755)
    print(f"Created Docker test script at {script_path}")


def create_dockerfile():
    """Create a Dockerfile for testing"""
    dockerfile_content = """FROM archlinux:base

# Install dependencies
RUN pacman -Syu --noconfirm && \\
    pacman -S --noconfirm base-devel git python python-pip

# Copy repository code
COPY . /app
WORKDIR /app

# Install Python dependencies
RUN pip install pytest

# Set up test environment
RUN mkdir -p /tmp/test_repo/x86_64 && \\
    mkdir -p /tmp/uploads

# Run tests
CMD ["python", "-m", "unittest", "test/api/test_archrepo_api.py"]
"""

    dockerfile_path = Path(__file__).parent / 'Dockerfile.test'
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)

    print(f"Created test Dockerfile at {dockerfile_path}")


if __name__ == "__main__":
    # Create docker test files
    create_docker_test_script()
    create_dockerfile()

    print("\nTo run tests in Docker:")
    print("1. Build the test image:")
    print("   docker build -f test/api/Dockerfile.test -t archrepo-test .")
    print("2. Run the tests:")
    print("   docker run --rm archrepo-test")

    # Run tests directly if not in Docker
    if os.environ.get('IN_DOCKER') != '1':
        print("\nRunning tests directly (not in Docker)...")
        unittest.main()
