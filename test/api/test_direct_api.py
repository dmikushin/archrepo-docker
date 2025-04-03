#!/usr/bin/env python3
"""
test_direct_api.py - Direct test suite for ArchRepo API

This test suite connects the archrepo.api.ArchRepoClient directly to
the mock_pkg_shell.py script without using SSH/network connections.
It implements a complete test harness for all API functions without
requiring network connectivity between client and server.
"""

import os
import sys
import unittest
import subprocess
import shutil
import base64
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import archrepo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from archrepo.api import ArchRepoClient


class DirectConnection:
    """Direct connection to mock_pkg_shell.py instead of SSH"""

    def __init__(self, shell_script, real_popen):
        self.shell_script = shell_script
        self.returncode = 0
        self.real_popen = real_popen  # Store the real Popen

    def communicate(self, input=None):
        """Run commands directly through the shell script"""
        process = self.real_popen(
            [self.shell_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env={
                "REPO_DIR": "/tmp/test_repo/x86_64",
                "DB_NAME": "repo.db.tar.gz",
                "UPLOAD_DIR": "/tmp/uploads",
                "PATH": os.environ.get("PATH")
            }
        )

        stdout, stderr = process.communicate(input=input)
        self.returncode = process.returncode

        return stdout, stderr


class TestDirectArchRepoAPI(unittest.TestCase):
    """Test suite for the ArchRepo API using direct connection without network"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests"""
        cls.test_dir = Path('/tmp/test_repo')
        cls.x86_64_dir = cls.test_dir / 'x86_64'
        cls.uploads_dir = Path('/tmp/uploads')

        # Ensure directories exist
        cls.x86_64_dir.mkdir(parents=True, exist_ok=True)
        cls.uploads_dir.mkdir(parents=True, exist_ok=True)

        # Path to the mock shell script
        cls.mock_shell = Path(__file__).parent / 'mock_pkg_shell.py'

        # Path to the dummy package
        cls.dummy_pkg = Path(__file__).parent / 'fixtures/test-package-1.0.0-1-x86_64.pkg.tar.zst'

        # Initialize repo if needed
        if not (cls.x86_64_dir / 'repo.db.tar.gz').exists():
            subprocess.run(['repo-add', str(cls.x86_64_dir / 'repo.db.tar.gz')],
                          check=True)

        # Ensure test package exists
        if not cls.dummy_pkg.exists():
            print(f"Warning: Test package not found at {cls.dummy_pkg}")
            print("Running generate_dummy_package.sh...")
            generator_script = Path(__file__).parent / 'generate_dummy_package.sh'
            if generator_script.exists():
                subprocess.run([str(generator_script)], check=True)
            else:
                raise FileNotFoundError(f"Could not find {generator_script}")

    def setUp(self):
        """Set up before each test"""
        self.client = ArchRepoClient(host="dummy-host")  # Host doesn't matter

        # Save a reference to the real Popen
        self.real_popen = subprocess.Popen

        # Patch the subprocess.Popen to use our direct connection
        self.popen_patcher = patch('subprocess.Popen')
        self.mock_popen = self.popen_patcher.start()

        # Configure the mock to return our DirectConnection instance
        self.direct_connection = DirectConnection(self.mock_shell, self.real_popen)
        self.mock_popen.return_value = self.direct_connection

    def tearDown(self):
        """Clean up after each test"""
        self.popen_patcher.stop()

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        # Clean up test repo files
        # Uncomment to clean up after tests; for now we keep them for inspection
        # shutil.rmtree(cls.test_dir, ignore_errors=True)
        # shutil.rmtree(cls.uploads_dir, ignore_errors=True)
        pass

    def test_publish_package(self):
        """Test publishing a package to the repository"""
        # Copy the test package to a location where it can be found
        test_pkg_path = self.uploads_dir / self.dummy_pkg.name
        shutil.copy(self.dummy_pkg, test_pkg_path)
        shutil.copy(f"{self.dummy_pkg}.sig", f"{test_pkg_path}.sig")

        # Test publishing with signature
        success, message = self.client.publish_package(str(test_pkg_path))
        self.assertTrue(success, f"Failed to publish package: {message}")
        self.assertIn("successfully", message.lower())

        # Test publishing without signature requirement
        os.remove(f"{test_pkg_path}.sig")  # Remove signature file
        success, message = self.client.publish_package(str(test_pkg_path), no_signing=True)
        self.assertTrue(success, f"Failed to publish package without signature: {message}")

    def test_list_packages(self):
        """Test listing packages in the repository"""
        # First ensure we have at least one package in the repo
        test_pkg_path = self.uploads_dir / self.dummy_pkg.name
        if not test_pkg_path.exists():
            shutil.copy(self.dummy_pkg, test_pkg_path)
            shutil.copy(f"{self.dummy_pkg}.sig", f"{test_pkg_path}.sig")
            self.client.publish_package(str(test_pkg_path))

        # Test listing packages
        success, packages = self.client.list_packages()
        self.assertTrue(success, "Failed to list packages")
        self.assertIsInstance(packages, list, "Packages should be a list")
        self.assertGreaterEqual(len(packages), 1, "Should have at least one package")

        # Verify package structure
        package = packages[0]
        self.assertIn('name', package, "Package should have 'name' field")
        self.assertIn('version', package, "Package should have 'version' field")
        self.assertIn('description', package, "Package should have 'description' field")

    def test_remove_package(self):
        """Test removing a package from the repository"""
        # First ensure we have the package in the repo
        test_pkg_path = self.uploads_dir / self.dummy_pkg.name
        if not test_pkg_path.exists():
            shutil.copy(self.dummy_pkg, test_pkg_path)
            shutil.copy(f"{self.dummy_pkg}.sig", f"{test_pkg_path}.sig")
            self.client.publish_package(str(test_pkg_path))

        # Extract package name (without version)
        pkg_name = 'test-package'  # Hardcoded for our test package

        # Test removing the package
        success, message = self.client.remove_package(pkg_name)
        self.assertTrue(success, f"Failed to remove package: {message}")
        self.assertIn("successfully", message.lower())

        # Verify package was removed by listing packages
        success, packages = self.client.list_packages()
        pkg_names = [p['name'] for p in packages]
        self.assertNotIn(pkg_name, pkg_names, f"Package {pkg_name} still in repo after removal")

    def test_clean_repository(self):
        """Test cleaning the repository of old package versions"""
        # Add multiple versions of the same package
        pkg_name = 'test-package'
        versions = ['1.0.0', '1.1.0', '1.2.0']

        for version in versions:
            # Create a dummy package for each version
            test_pkg_path = self.uploads_dir / f"{pkg_name}-{version}-1-x86_64.pkg.tar.zst"
            with open(test_pkg_path, 'w') as f:
                f.write(f"Test package version {version}")

            # Create a dummy signature
            with open(f"{test_pkg_path}.sig", 'w') as f:
                f.write(f"Test signature for version {version}")

            # Publish it
            self.client.publish_package(str(test_pkg_path), no_signing=True)

        # Clean the repository
        success, message = self.client.clean_repository()
        self.assertTrue(success, f"Failed to clean repository: {message}")
        self.assertIn("successfully", message.lower())

    def test_get_status(self):
        """Test getting repository status information"""
        # First ensure we have at least one package in the repo
        test_pkg_path = self.uploads_dir / self.dummy_pkg.name
        if not test_pkg_path.exists():
            shutil.copy(self.dummy_pkg, test_pkg_path)
            self.client.publish_package(str(test_pkg_path), no_signing=True)

        # Test getting status
        success, status = self.client.get_status()
        self.assertTrue(success, f"Failed to get repository status")
        self.assertIsInstance(status, dict, "Status should be a dictionary")

        # Check for expected keys
        expected_keys = ['Total packages', 'Repository size', 'Last database update']
        for key in expected_keys:
            self.assertIn(key, status, f"Status should include '{key}'")


if __name__ == '__main__':
    unittest.main()
