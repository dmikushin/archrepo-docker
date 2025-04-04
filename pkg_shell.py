#!/usr/bin/env python3
"""
pkg_shell.py - Custom shell for pkguser that provides repository management functions
"""

import os
import sys
import base64
import subprocess
import re
import datetime
import tempfile
from pathlib import Path


class PackageRepositoryShell:
    """Primary Package Repository Shell"""

    def __init__(self):
        """Initialize the shell with configuration and required directories"""
        # Configuration from environment variables with defaults
        self.repo_dir = os.environ.get("REPO_DIR", "/srv/repo/x86_64")
        self.db_name = os.environ.get("DB_NAME", "repo.db.tar.gz")
        self.upload_dir = os.environ.get("UPLOAD_DIR", os.path.expanduser("~/uploads"))
        self.history_file = os.environ.get("HISTORY_FILE", os.path.expanduser("~/.pkg_shell_history"))

        # Create required directories
        os.makedirs(self.repo_dir, exist_ok=True)
        os.makedirs(self.upload_dir, exist_ok=True)
        Path(self.history_file).touch(exist_ok=True)

        # Initialize repository database if it doesn't exist
        self._initialize_repo_database()

    def show_welcome(self):
        """Display welcome message"""
        print("================================================================")
        print("                 ARCH REPOSITORY MANAGEMENT SHELL                ")
        print("================================================================")
        print("Type 'help' to see available commands")
        print()

    def show_help(self):
        """Display help menu"""
        print("Available commands:")
        print("  add <package-file.pkg.tar.zst>  - Add a package to the repository")
        print("  remove <package-name>           - Remove a package from the repository")
        print("  list                            - List all packages in the repository")
        print("  clean                           - Clean up old package versions")
        print("  receive <filename>              - Receive a package file through the SSH connection")
        print("  send <filename>                 - Send a file from the repository to the client")
        print("  status                          - Show repository statistics")
        print("  help                            - Show this help message")
        print("  exit                            - Log out")
        print()

    def add_package(self, pkg_path):
        """Add a package to the repository"""
        if not pkg_path:
            print("Error: No package specified")
            print("Usage: add <package-file.pkg.tar.zst>")
            return False

        # Check if package exists in current location or repo
        pkg_exists = os.path.isfile(pkg_path)
        repo_pkg_path = os.path.join(self.repo_dir, os.path.basename(pkg_path))
        repo_pkg_exists = os.path.isfile(repo_pkg_path)

        if not pkg_exists and not repo_pkg_exists:
            print(f"Error: Package file not found: {pkg_path}")
            print("Note: Package must be in the current directory or already in the repository")
            return False

        # If package is not in repo, copy it there
        if not repo_pkg_exists:
            print("Copying package to repository...")
            subprocess.run(["cp", pkg_path, self.repo_dir])
            pkg_file = os.path.basename(pkg_path)

            # Also copy signature file if it exists
            sig_path = f"{pkg_path}.sig"
            upload_sig_path = os.path.join(self.upload_dir, f"{pkg_file}.sig")

            if os.path.isfile(sig_path):
                print("Copying signature file to repository...")
                subprocess.run(["cp", sig_path, f"{self.repo_dir}/{pkg_file}.sig"])
            elif os.path.isfile(upload_sig_path):
                print("Copying signature file from uploads to repository...")
                subprocess.run(["cp", upload_sig_path, f"{self.repo_dir}/{pkg_file}.sig"])
        else:
            pkg_file = os.path.basename(pkg_path)

        # Update the repository database
        print("Updating repository database...")
        current_dir = os.getcwd()
        os.chdir(self.repo_dir)

        try:
            subprocess.run(["repo-add", self.db_name, pkg_file], check=True)
            print("Package added successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error adding package to repository: {e}")
            return False
        finally:
            os.chdir(current_dir)

    def remove_package(self, pkg_name):
        """Remove a package from the repository"""
        if not pkg_name:
            print("Error: No package specified")
            print("Usage: remove <package-name>")
            return False

        current_dir = os.getcwd()
        os.chdir(self.repo_dir)

        try:
            # Check if package exists in database
            result = subprocess.run(
                ["pacman", "-Sl", "custom"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print("Error checking repository contents")
                return False

            if not any(re.search(rf"\bcustom\s+{re.escape(pkg_name)}\b", line) for line in result.stdout.splitlines()):
                print(f"Error: Package not found in repository: {pkg_name}")
                return False

            # Remove package from database
            print("Removing package from database...")
            subprocess.run(["repo-remove", self.db_name, pkg_name], check=True)

            # Remove package files and signatures
            print("Removing package files and signatures...")
            pkg_files = list(Path(self.repo_dir).glob(f"{pkg_name}-*.pkg.tar.zst"))
            sig_files = list(Path(self.repo_dir).glob(f"{pkg_name}-*.pkg.tar.zst.sig"))

            for f in pkg_files + sig_files:
                print(f"Removing {f.name}")
                f.unlink()

            print("Package removed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error removing package: {e}")
            return False
        finally:
            os.chdir(current_dir)

    def list_packages(self):
        """List all packages in the repository"""
        print("Packages in repository:")
        print("----------------------")

        current_dir = os.getcwd()
        os.chdir(self.repo_dir)

        try:
            result = subprocess.run(
                ["pacman", "-Sl", "custom"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print("Error listing packages")
                return False

            print(result.stdout.strip())

            # Count packages
            count = len(result.stdout.splitlines())
            print("----------------------")
            print(f"Total packages: {count}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error listing packages: {e}")
            return False
        finally:
            os.chdir(current_dir)

    def clean_repo(self):
        """Clean repository by removing old package versions"""
        print("Cleaning repository...")

        current_dir = os.getcwd()
        os.chdir(self.repo_dir)

        try:
            cleaned = 0
            pkg_files = list(Path(self.repo_dir).glob("*.pkg.tar.zst"))

            # Get unique package names
            pkg_names = set()
            for pkg_file in pkg_files:
                # Extract package name (without version)
                pkg_name = re.sub(r'-[0-9].*$', '', pkg_file.name)
                pkg_names.add(pkg_name)

            # For each package name, find and keep only the latest version
            for pkg_name in pkg_names:
                versions = sorted(Path(self.repo_dir).glob(f"{pkg_name}-*.pkg.tar.zst"))
                if len(versions) > 1:
                    print(f"Cleaning old versions of {pkg_name}...")
                    # Keep only the latest version (last in sorted list)
                    for old_version in versions[:-1]:
                        print(f"Removing {old_version.name}")
                        old_version.unlink(missing_ok=True)
                        sig_file = Path(f"{old_version}.sig")
                        sig_file.unlink(missing_ok=True)
                        cleaned += 1

            # Rebuild the database
            print("Rebuilding repository database...")
            pkg_files = list(Path(self.repo_dir).glob("*.pkg.tar.zst"))
            if pkg_files:
                subprocess.run(["repo-add", "-f", self.db_name] +
                              [str(f) for f in pkg_files],
                              check=True)
            else:
                # Create empty database if no packages exist
                subprocess.run(["repo-add", "-f", self.db_name], check=True)

            print(f"Repository cleaned successfully. Removed {cleaned} old package versions.")
            return True
        except Exception as e:
            print(f"Error cleaning repository: {e}")
            return False
        finally:
            os.chdir(current_dir)

    def show_status(self):
        """Show status of the repository"""
        print("Repository Status:")
        print("-----------------")

        current_dir = os.getcwd()
        os.chdir(self.repo_dir)

        try:
            # Count packages
            pkg_count = len(list(Path(self.repo_dir).glob("*.pkg.tar.zst")))
            print(f"Total packages: {pkg_count}")

            # Count signatures
            sig_count = len(list(Path(self.repo_dir).glob("*.pkg.tar.zst.sig")))
            print(f"Signed packages: {sig_count}")

            # Repository size
            repo_size = subprocess.run(
                ["du", "-sh", self.repo_dir],
                capture_output=True,
                text=True
            ).stdout.split()[0]
            print(f"Repository size: {repo_size}")

            # Last update time
            try:
                db_path = Path(self.repo_dir) / self.db_name
                if db_path.exists():
                    last_update = datetime.datetime.fromtimestamp(db_path.stat().st_mtime)
                    print(f"Last database update: {last_update}")
                else:
                    print("Last database update: Never")
            except Exception:
                print("Last database update: Unknown")

            # Disk space
            disk_info = subprocess.run(
                ["df", "-h", self.repo_dir],
                capture_output=True,
                text=True
            ).stdout.splitlines()
            if len(disk_info) > 1:
                disk_usage = disk_info[1].split()
                print("Disk usage:")
                print(f"  Filesystem: {disk_usage[0]}, Size: {disk_usage[1]}, "
                      f"Used: {disk_usage[2]}, Avail: {disk_usage[3]}, Use%: {disk_usage[4]}")

            return True
        except Exception as e:
            print(f"Error getting repository status: {e}")
            return False
        finally:
            os.chdir(current_dir)

    def receive_file(self, filename):
        """Receive a file through SSH"""
        if not filename:
            print("Error: No filename specified")
            print("Usage: receive <filename>")
            return False

        is_signature = filename.endswith('.sig')

        print(f"Ready to receive file: {filename}")
        print("Please paste the base64-encoded file content and end with a line containing only 'EOF'")
        print("Waiting for data...")

        # Create a temporary file to store the base64 data
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as b64file:
            b64file_path = b64file.name

            # Read input until we get the EOF marker
            while True:
                try:
                    line = input()
                    if line == "EOF":
                        break
                    b64file.write(line + "\n")
                except EOFError:
                    # Handle EOF in non-interactive mode
                    break

        try:
            # Decode the base64 data to the actual file
            output_path = os.path.join(self.upload_dir, filename)
            with open(b64file_path, 'r') as b64file, open(output_path, 'wb') as outfile:
                base64_data = b64file.read()
                binary_data = base64.b64decode(base64_data)
                outfile.write(binary_data)

            # Check if the file was created successfully
            if os.path.isfile(output_path):
                if is_signature:
                    print(f"Signature file received successfully: {filename}")
                else:
                    print(f"File received successfully: {filename}")

                # Get file size
                file_size = subprocess.run(
                    ["du", "-h", output_path],
                    capture_output=True,
                    text=True
                ).stdout.split()[0]
                print(f"Size: {file_size}")

                if not is_signature:
                    print(f"Use 'add {output_path}' to add it to the repository")
                return True
            else:
                print("Error: Failed to receive file.")
                return False
        except Exception as e:
            print(f"Error receiving file: {e}")
            return False
        finally:
            # Clean up the temporary base64 file
            if os.path.exists(b64file_path):
                os.unlink(b64file_path)

    def send_file(self, filename):
        """Send a file through SSH"""
        if not filename:
            print("Error: No filename specified")
            print("Usage: send <filename>")
            return False

        # Find the file
        file_path = None

        # Check in repo
        repo_path = os.path.join(self.repo_dir, filename)
        if os.path.isfile(repo_path):
            file_path = repo_path
        # Check in uploads
        elif os.path.isfile(os.path.join(self.upload_dir, filename)):
            file_path = os.path.join(self.upload_dir, filename)
        # Check if it's a full path
        elif os.path.isfile(filename):
            file_path = filename

        if not file_path:
            print(f"Error: File not found: {filename}")
            print("The file must be in the repository, uploads directory, or you must specify a full path.")
            return False

        # Get file size
        file_size = subprocess.run(
            ["du", "-h", file_path],
            capture_output=True,
            text=True
        ).stdout.split()[0]

        print(f"Sending file: {os.path.basename(file_path)}")
        print(f"Size: {file_size}")
        print("Base64 encoded data follows (copy everything between START and END markers):")
        print("-----START FILE DATA-----")

        # Read and encode the file
        with open(file_path, 'rb') as f:
            encoded_data = base64.b64encode(f.read()).decode('utf-8')
            print(encoded_data)

        print("-----END FILE DATA-----")
        print("")
        print("To save this file on your local machine:")
        print("1. Copy all the data between the START and END markers")
        print("2. Run this command in your local terminal:")
        print(f"   echo 'PASTE_DATA_HERE' | base64 -d > {os.path.basename(file_path)}")

        return True

    def log_command(self, command):
        """Log command to history file"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.history_file, 'a') as f:
            f.write(f"{timestamp} - {command}\n")

    def process_command(self, cmd, args):
        """Process a single command"""
        if cmd == "add":
            return self.add_package(args)
        elif cmd == "remove":
            return self.remove_package(args)
        elif cmd == "list":
            return self.list_packages()
        elif cmd == "clean":
            return self.clean_repo()
        elif cmd == "status":
            return self.show_status()
        elif cmd == "receive":
            return self.receive_file(args)
        elif cmd == "send":
            return self.send_file(args)
        elif cmd == "help":
            self.show_help()
            return True
        elif cmd in ["exit", "quit", "logout"]:
            print("Logging out...")
            return None  # Signal to exit
        else:
            print(f"Unknown command: {cmd}")
            print("Type 'help' for a list of available commands")
            return False

    def main_loop(self):
        """Main interactive loop"""
        self.show_welcome()

        while True:
            try:
                # Print prompt
                cmd_input = input("pkgrepo> ").strip()

                # Skip empty commands
                if not cmd_input:
                    continue

                # Parse command and arguments
                parts = cmd_input.split(maxsplit=1)
                cmd = parts[0]
                args = parts[1] if len(parts) > 1 else ""

                # Log command (except exit)
                if cmd != "exit":
                    self.log_command(cmd_input)

                # Process command
                result = self.process_command(cmd, args)
                if result is None:  # Exit signal
                    break

                print()  # Empty line after each command
            except KeyboardInterrupt:
                print("\nInterrupted. Type 'exit' to quit.")
            except EOFError:
                print("\nEnd of input. Exiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

    def process_stdin(self):
        """Process commands from standard input (non-interactive mode)"""
        for line in sys.stdin:
            line = line.strip()
            if not line or line == "exit":
                continue

            parts = line.split(maxsplit=1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""

            self.process_command(cmd, args)
            print()  # Empty line after each command

    def _initialize_repo_database(self):
        """Initialize repository database if it doesn't exist"""
        db_path = os.path.join(self.repo_dir, self.db_name)
        if not os.path.exists(db_path):
            print(f"Initializing empty repository database at {db_path}...")
            current_dir = os.getcwd()
            try:
                os.chdir(self.repo_dir)
                subprocess.run(["repo-add", self.db_name], check=True)
                print("Repository database initialized successfully.")
            except subprocess.CalledProcessError as e:
                print(f"Error initializing repository database: {e}")
            except Exception as e:
                print(f"Unexpected error initializing repository: {e}")
            finally:
                os.chdir(current_dir)


if __name__ == "__main__":
    shell = PackageRepositoryShell()
    # Handle non-interactive mode
    if not sys.stdin.isatty():
        shell.process_stdin()
    else:
        shell.main_loop()
