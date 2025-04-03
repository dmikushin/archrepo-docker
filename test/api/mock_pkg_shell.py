#!/usr/bin/env python3
"""
mock_pkg_shell.py - Mock implementation of package repository shell for testing

This module inherits directly from the pkg_shell.py implementation and
only overrides the necessary configuration for testing.
"""

import os
import sys
import subprocess
from pathlib import Path
from pkg_shell import PackageRepositoryShell


class MockPackageRepositoryShell(PackageRepositoryShell):
    """Mock Package Repository Shell for Testing"""

    def __init__(self):
        """Initialize with test settings"""
        super().__init__()
        # Override configuration for testing
        self.repo_dir = os.environ.get("REPO_DIR", "/tmp/test_repo/x86_64")
        self.db_name = os.environ.get("DB_NAME", "repo.db.tar.gz")
        self.upload_dir = os.environ.get("UPLOAD_DIR", "/tmp/uploads")
        self.history_file = "/tmp/pkg_shell_test_history"

        # Create required directories
        os.makedirs(self.repo_dir, exist_ok=True)
        os.makedirs(self.upload_dir, exist_ok=True)

        # Initialize repo if needed
        db_path = os.path.join(self.repo_dir, self.db_name)
        if not os.path.isfile(db_path):
            print(f"Initializing test repository at {db_path}...")
            try:
                subprocess.run(["repo-add", db_path], check=False)
            except Exception as e:
                print(f"Warning: Could not initialize repo: {e}")


if __name__ == "__main__":
    shell = MockPackageRepositoryShell()
    # Always run in non-interactive mode for testing
    shell.process_stdin()
