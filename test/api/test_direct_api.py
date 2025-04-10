#!/usr/bin/env python3
"""
test_direct_api.py - Direct test suite for ArchRepo API

This test suite connects the archrepo.api.ArchRepoClient directly to
the pkg_shell.py script without using SSH/network connections.
It implements a complete test harness for all API functions without
requiring network connectivity between client and server.
"""

import os
import sys
import unittest
import subprocess
import shutil
import base64
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock
import pty

# Add parent directory to path so we can import archrepo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from archrepo.api import ArchRepoClient


class CustomTestResult(unittest.TextTestResult):
    """Custom test result class that includes error log in failure messages"""

    def __init__(self, stream, descriptions, verbosity, error_log_file, debug_on_failure=False, real_popen=None):
        super().__init__(stream, descriptions, verbosity)
        self.error_log_file = error_log_file
        self.debug_on_failure = debug_on_failure
        self.real_popen = real_popen  # Store the reference to the real Popen

    def _get_error_log_content(self):
        """Get the content of the error log file"""
        if not Path(self.error_log_file).exists():
            return "Error log file does not exist."

        try:
            with open(self.error_log_file, 'r') as f:
                return f.read().strip()
        except Exception as e:
            return f"Error reading log file: {e}"

    def _debug_failure(self, test, err, failure_type="ERROR"):
        """Launch debug shell when a failure occurs"""
        if self.debug_on_failure:
            print(f"\n\n===== TEST {failure_type} =====")
            print(f"Test: {test}")
            print(f"Error: {err[1]}")
            print("\nSystem state when failure occurred:")

            # Temporarily restore the original subprocess.Popen
            original_popen = subprocess.Popen
            subprocess.Popen = self.real_popen

            try:
                subprocess.call(['ls', '-la', '/tmp/test_repo/x86_64'])
                print("\nDropping into bash shell for debugging...")
                print("Type 'exit' when finished to continue with the test suite.")

                # Use pty to allocate a pseudo-terminal
                pid, fd = pty.fork()
                if pid == 0:
                    # Child process
                    os.execvp('bash', ['bash', '-i'])
                else:
                    # Parent process
                    os.waitpid(pid, 0)

                print("\nResuming test execution...")

            finally:
                # Restore our mocked version after debugging
                subprocess.Popen = original_popen

    def addFailure(self, test, err):
        """Add failure with error log included"""
        log_content = self._get_error_log_content()
        if log_content != "":
            err = (err[0], AssertionError(f"{str(err[1])}\n\n===== ERROR LOG =====\n{log_content}\n====================="), err[2])
        super().addFailure(test, err)
        self._debug_failure(test, err, "FAILED")

    def addError(self, test, err):
        """Add error with error log included"""
        log_content = self._get_error_log_content()
        if log_content != "":
            err = (err[0], type(err[1])(f"{str(err[1])}\n\n===== ERROR LOG =====\n{log_content}\n====================="), err[2])
        super().addError(test, err)
        self._debug_failure(test, err, "ERROR")


class CustomTestRunner(unittest.TextTestRunner):
    """Custom test runner that uses our CustomTestResult"""

    def __init__(self, error_log_file, debug_on_failure=False, real_popen=None, **kwargs):
        super().__init__(**kwargs)
        self.error_log_file = error_log_file
        self.debug_on_failure = debug_on_failure
        self.real_popen = real_popen

    def _makeResult(self):
        return CustomTestResult(self.stream, self.descriptions, self.verbosity,
                               self.error_log_file, self.debug_on_failure, self.real_popen)


class DirectConnection:
    """Direct connection to pkg_shell.py instead of SSH"""

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
                "DB_NAME": "repo.db.tar.zst",
                "UPLOAD_DIR": "/tmp/uploads",
                "HISTORY_FILE": "/tmp/pkg_shell_test_history",
                "ERROR_LOG_FILE": "/tmp/pkg_shell_direct_test_errors.log",
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

        # Path to pkg_shell.py (main script, not mock)
        cls.pkg_shell = 'pkg_shell'

        # Define error log file path
        cls.error_log_file = Path('/tmp/pkg_shell_direct_test_errors.log')

        # Path to the dummy package
        cls.dummy_pkg = Path(__file__).parent / 'fixtures/test-package-1.0.0-1-x86_64.pkg.tar.zst'

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
        # Clear the error log before each test
        self._clear_error_log()

        self.client = ArchRepoClient(host="dummy-host")  # Host doesn't matter

        # Save a reference to the real Popen
        self.real_popen = subprocess.Popen

        # Patch the subprocess.Popen to use our direct connection
        self.popen_patcher = patch('subprocess.Popen')
        self.mock_popen = self.popen_patcher.start()

        # Configure the mock to return our DirectConnection instance
        self.direct_connection = DirectConnection(self.pkg_shell, self.real_popen)
        self.mock_popen.return_value = self.direct_connection

    def tearDown(self):
        """Clean up after each test"""
        self.popen_patcher.stop()

    def _clear_error_log(self):
        """Clear the error log file before each test"""
        # Create an empty error log file or truncate existing one
        with open(self.error_log_file, 'w') as f:
            pass

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        # Clean up test repo files
        # Comment to keep files for inspection, uncomment to clean up
        # shutil.rmtree(cls.test_dir, ignore_errors=True)
        # shutil.rmtree(cls.uploads_dir, ignore_errors=True)

        # Remove error log file
        if cls.error_log_file.exists():
            cls.error_log_file.unlink()

    def test_publish_package(self):
        """Test publishing a package to the repository"""
        # Copy the test package to a location where it can be found
        test_pkg_path = self.uploads_dir / self.dummy_pkg.name
        shutil.copy(self.dummy_pkg, test_pkg_path)
        shutil.copy(f"{self.dummy_pkg}.sig", f"{test_pkg_path}.sig")

        # Test publishing with signature
        success, message = self.client.publish_package(str(test_pkg_path))
        if not success:
            self.fail(f"Failed to publish package: {message}")

        self.assertIn("successfully", message.lower())

        # Test publishing without signature requirement
        os.remove(f"{test_pkg_path}.sig")  # Remove signature file
        success, message = self.client.publish_package(str(test_pkg_path), no_signing=True)
        if not success:
            self.fail(f"Failed to publish package without signature: {message}")

    def test_list_packages(self):
        """Test listing packages in the repository"""
        # First ensure we have at least one package in the repo
        test_pkg_path = self.uploads_dir / self.dummy_pkg.name
        if not test_pkg_path.exists():
            shutil.copy(self.dummy_pkg, test_pkg_path)
            shutil.copy(f"{self.dummy_pkg}.sig", f"{test_pkg_path}.sig")
            success, message = self.client.publish_package(str(test_pkg_path))
            if not success:
                self.fail(f"Failed to setup package for listing: {message}")

        # Test listing packages
        success, packages = self.client.list_packages()
        if not success:
            self.fail("Failed to list packages")

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
            success, message = self.client.publish_package(str(test_pkg_path))
            if not success:
                self.fail(f"Failed to setup package for removal: {message}")

        # Extract package name (without version)
        pkg_name = 'test-package'  # Hardcoded for our test package

        # Test removing the package
        success, message = self.client.remove_package(pkg_name)
        if not success:
            self.fail(f"Failed to remove package: {message}")

        self.assertIn("successfully", message.lower())

        # Verify package was removed by listing packages
        success, packages = self.client.list_packages()
        if not success:
            self.fail("Failed to verify package removal")

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
            success, message = self.client.publish_package(str(test_pkg_path), no_signing=True)
            if not success:
                self.fail(f"Failed to setup package version {version} for cleaning: {message}")

        # Clean the repository
        success, message = self.client.clean_repository()
        if not success:
            self.fail(f"Failed to clean repository: {message}")

        self.assertIn("successfully", message.lower())

        # Count package files after cleaning
        version_files = list(self.x86_64_dir.glob(f"{pkg_name}-*.pkg.tar.zst"))
        self.assertEqual(len(version_files), 1, f"Expected only one package version after cleaning, found {len(version_files)}")

        # Check it's the latest version
        latest_version = '1.2.0'
        latest_pkg_filename = f"{pkg_name}-{latest_version}-1-x86_64.pkg.tar.zst"
        self.assertTrue(any(latest_pkg_filename in str(f) for f in version_files),
                       f"Expected to find latest version {latest_version} in {[f.name for f in version_files]}")

    def test_get_status(self):
        """Test getting repository status information"""
        # First ensure we have at least one package in the repo
        test_pkg_path = self.uploads_dir / self.dummy_pkg.name
        if not test_pkg_path.exists():
            shutil.copy(self.dummy_pkg, test_pkg_path)
            success, message = self.client.publish_package(str(test_pkg_path), no_signing=True)
            if not success:
                self.fail(f"Failed to setup package for status: {message}")

        # Test getting status
        success, status = self.client.get_status()
        if not success:
            self.fail(f"Failed to get repository status")

        self.assertIsInstance(status, dict, "Status should be a dictionary")

        # Check for expected keys
        expected_keys = ['Total packages']
        for key in expected_keys:
            self.assertIn(key, status, f"Status should include '{key}'")


if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run ArchRepo API tests")
    parser.add_argument("--debug-on-failure", action="store_true",
                        help="Drop into a bash shell when a test fails")

    # Also support environment variable for CI or script usage
    env_debug = os.environ.get('DEBUG_ON_FAILURE', '').lower() in ('true', '1', 'yes')

    # Parse only the known arguments, leaving the rest for unittest.main()
    args, unknown = parser.parse_known_args()

    # Use either command line flag or environment variable
    debug_on_failure = args.debug_on_failure or env_debug

    # Update sys.argv to remove our custom arguments
    sys.argv = [sys.argv[0]] + unknown

    # Store reference to the real subprocess.Popen before any patches
    real_popen = subprocess.Popen

    # Use our custom test runner with the error log file path and real_popen reference
    runner = CustomTestRunner(
        error_log_file='/tmp/pkg_shell_direct_test_errors.log',
        debug_on_failure=debug_on_failure,
        real_popen=real_popen,
        verbosity=2
    )
    unittest.main(testRunner=runner)
