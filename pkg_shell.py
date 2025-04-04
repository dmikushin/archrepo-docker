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
import traceback
import logging
from pathlib import Path


class PackageRepositoryShell:
    """Primary Package Repository Shell"""

    def __init__(self):
        """Initialize the shell with configuration and required directories"""
        # Configuration from environment variables with defaults
        self.repo_dir = os.environ.get("REPO_DIR", "/srv/repo/x86_64")
        self.db_name = os.environ.get("DB_NAME", "repo.db.tar.zst")
        self.upload_dir = os.environ.get("UPLOAD_DIR", os.path.expanduser("~/uploads"))
        self.history_file = os.environ.get("HISTORY_FILE", os.path.expanduser("~/.pkg_shell_history"))
        self.error_log_file = os.environ.get("ERROR_LOG_FILE", os.path.expanduser("~/.pkg_shell_errors.log"))

        # Set up logging
        self._setup_logging()

        # Create required directories
        os.makedirs(self.repo_dir, exist_ok=True)
        os.makedirs(self.upload_dir, exist_ok=True)
        Path(self.history_file).touch(exist_ok=True)

        # Initialize repository database if it doesn't exist
        self._initialize_repo_database()

    def _setup_logging(self):
        """Set up logging configuration"""
        # Create a logger
        self.logger = logging.getLogger("pkg_shell")
        self.logger.setLevel(logging.DEBUG)

        # Create file handler for error log
        file_handler = logging.FileHandler(self.error_log_file)
        file_handler.setLevel(logging.DEBUG)

        # Create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        # Add the handlers to the logger
        self.logger.addHandler(file_handler)

    def log_error(self, command, error, detail=None):
        """Log an error with details and return formatted error message"""
        # Get the current timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Log to error log file
        error_message = f"Command: {command} | Error: {error}"
        if detail:
            error_message += f" | Detail: {detail}"
        self.logger.error(error_message)

        # Format user-facing error message
        user_message = f"Error: {error}"
        if detail:
            user_message += f"\nDetail: {detail}"
        user_message += f"\n[Error logged at {timestamp}]"
        user_message += f"\nError log file: {self.error_log_file}"

        return user_message

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
        print("  errors                          - Show recent error logs")
        print("  help                            - Show this help message")
        print("  exit                            - Log out")
        print()

    def show_recent_errors(self, count=10):
        """Show recent errors from the error log"""
        try:
            if not os.path.exists(self.error_log_file) or os.path.getsize(self.error_log_file) == 0:
                print("No errors logged yet.")
                return True

            print(f"Recent errors (last {count}):")
            print("-" * 70)

            with open(self.error_log_file, 'r') as f:
                lines = f.readlines()

            # Show the last 'count' lines
            for line in lines[-count:]:
                print(line.strip())

            print("-" * 70)
            return True
        except Exception as e:
            error_msg = self.log_error("errors", f"Failed to read error log: {e}",
                                       traceback.format_exc())
            print(error_msg)
            return False

    def add_package(self, pkg_path):
        """Add a package to the repository"""
        cmd = f"add {pkg_path}"

        if not pkg_path:
            error_msg = self.log_error(cmd, "No package specified",
                                      "Command requires a package file path")
            print(error_msg)
            print("Usage: add <package-file.pkg.tar.zst>")
            return False

        # Check if package exists in current location or repo
        pkg_exists = os.path.isfile(pkg_path)
        repo_pkg_path = os.path.join(self.repo_dir, os.path.basename(pkg_path))
        repo_pkg_exists = os.path.isfile(repo_pkg_path)

        if not pkg_exists and not repo_pkg_exists:
            error_msg = self.log_error(cmd, f"Package file not found: {pkg_path}",
                                      f"Checked paths: {pkg_path}, {repo_pkg_path}")
            print(error_msg)
            print("Note: Package must be in the current directory or already in the repository")
            return False

        # If package is not in repo, copy it there
        if not repo_pkg_exists:
            print("Copying package to repository...")
            try:
                subprocess.run(["cp", pkg_path, self.repo_dir], check=True)
            except subprocess.CalledProcessError as e:
                error_msg = self.log_error(cmd, f"Failed to copy package to repository",
                                         f"Command: cp {pkg_path} {self.repo_dir}, Error: {e}, Return code: {e.returncode}")
                print(error_msg)
                return False

            pkg_file = os.path.basename(pkg_path)

            # Also copy signature file if it exists
            sig_path = f"{pkg_path}.sig"
            upload_sig_path = os.path.join(self.upload_dir, f"{pkg_file}.sig")

            if os.path.isfile(sig_path):
                print("Copying signature file to repository...")
                try:
                    subprocess.run(["cp", sig_path, f"{self.repo_dir}/{pkg_file}.sig"], check=True)
                except subprocess.CalledProcessError as e:
                    self.logger.warning(f"Failed to copy signature file: {e}")
                    print(f"Warning: Failed to copy signature file: {e}")
            elif os.path.isfile(upload_sig_path):
                print("Copying signature file from uploads to repository...")
                try:
                    subprocess.run(["cp", upload_sig_path, f"{self.repo_dir}/{pkg_file}.sig"], check=True)
                except subprocess.CalledProcessError as e:
                    self.logger.warning(f"Failed to copy uploaded signature file: {e}")
                    print(f"Warning: Failed to copy uploaded signature file: {e}")
        else:
            pkg_file = os.path.basename(pkg_path)

        # Update the repository database
        print("Updating repository database...")
        current_dir = os.getcwd()
        os.chdir(self.repo_dir)

        try:
            process = subprocess.run(["repo-add", self.db_name, pkg_file],
                                    check=True, capture_output=True, text=True)
            print("Package added successfully.")
            self.logger.info(f"Successfully added package: {pkg_file}")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = self.log_error(cmd, f"Error adding package to repository",
                                     f"Command: repo-add {self.db_name} {pkg_file}, "
                                     f"Return code: {e.returncode}, "
                                     f"Stdout: {e.stdout}, Stderr: {e.stderr}")
            print(error_msg)
            return False
        except Exception as e:
            error_msg = self.log_error(cmd, f"Unexpected error adding package",
                                     traceback.format_exc())
            print(error_msg)
            return False
        finally:
            os.chdir(current_dir)

    def remove_package(self, pkg_name):
        """Remove a package from the repository"""
        cmd = f"remove {pkg_name}"

        if not pkg_name:
            error_msg = self.log_error(cmd, "No package specified",
                                      "Command requires a package name")
            print(error_msg)
            print("Usage: remove <package-name>")
            return False

        current_dir = os.getcwd()
        os.chdir(self.repo_dir)

        try:
            # Check if package exists in database using the configured repo repository
            result = subprocess.run(
                ["pacman", "-Syl", "repo"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                error_msg = self.log_error(cmd, "Error checking repository contents",
                                         f"Command: pacman -Syl repo, "
                                         f"Return code: {result.returncode}, "
                                         f"Stderr: {result.stderr}")
                print(error_msg)
                return False

            if not any(re.search(rf"\brepo\s+{re.escape(pkg_name)}\b", line) for line in result.stdout.splitlines()):
                error_msg = self.log_error(cmd, f"Package not found in repository: {pkg_name}",
                                         f"Available packages: {result.stdout}")
                print(error_msg)
                return False

            # Remove package from database
            print("Removing package from database...")
            process = subprocess.run(
                ["repo-remove", self.db_name, pkg_name],
                check=True,
                capture_output=True,
                text=True
            )

            # Remove package files and signatures
            print("Removing package files and signatures...")
            pkg_files = list(Path(self.repo_dir).glob(f"{pkg_name}-*.pkg.tar.zst"))
            sig_files = list(Path(self.repo_dir).glob(f"{pkg_name}-*.pkg.tar.zst.sig"))

            if not pkg_files:
                self.logger.warning(f"No package files found for {pkg_name}")
                print(f"Warning: No package files found for {pkg_name}")

            removed_files = []
            for f in pkg_files + sig_files:
                try:
                    print(f"Removing {f.name}")
                    f.unlink()
                    removed_files.append(f.name)
                except Exception as e:
                    self.logger.warning(f"Failed to remove file {f.name}: {e}")
                    print(f"Warning: Failed to remove file {f.name}: {e}")

            print("Package removed successfully.")
            self.logger.info(f"Successfully removed package: {pkg_name}, "
                           f"Removed files: {', '.join(removed_files)}")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = self.log_error(cmd, f"Error removing package",
                                     f"Command: repo-remove {self.db_name} {pkg_name}, "
                                     f"Return code: {e.returncode}, "
                                     f"Stdout: {e.stdout}, Stderr: {e.stderr}")
            print(error_msg)
            return False
        except Exception as e:
            error_msg = self.log_error(cmd, f"Unexpected error removing package",
                                     traceback.format_exc())
            print(error_msg)
            return False
        finally:
            os.chdir(current_dir)

    def list_packages(self):
        """List all packages in the repository"""
        cmd = "list"

        print("Packages in repository:")
        print("----------------------")

        current_dir = os.getcwd()
        os.chdir(self.repo_dir)

        try:
            # Use pacman -Syl repo with the properly configured repository
            result = subprocess.run(
                ["pacman", "-Syl", "repo"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                error_msg = self.log_error(cmd, "Error listing packages",
                                         f"Command: pacman -Syl repo, "
                                         f"Return code: {result.returncode}, "
                                         f"Stderr: {result.stderr}")
                print(error_msg)
                return False

            print(result.stdout.strip())

            # Count packages
            count = len(result.stdout.splitlines())
            print("----------------------")
            print(f"Total packages: {count}")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = self.log_error(cmd, f"Error listing packages",
                                     f"Return code: {e.returncode}, "
                                     f"Stdout: {e.stdout}, Stderr: {e.stderr}")
            print(error_msg)
            return False
        except Exception as e:
            error_msg = self.log_error(cmd, f"Unexpected error listing packages",
                                     traceback.format_exc())
            print(error_msg)
            return False
        finally:
            os.chdir(current_dir)

    def clean_repo(self):
        """Clean repository by removing old package versions"""
        cmd = "clean"

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
                        try:
                            old_version.unlink(missing_ok=True)
                            sig_file = Path(f"{old_version}.sig")
                            sig_file.unlink(missing_ok=True)
                            cleaned += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to remove old version {old_version.name}: {e}")
                            print(f"Warning: Failed to remove old version {old_version.name}: {e}")

            # Rebuild the database
            print("Rebuilding repository database...")
            pkg_files = list(Path(self.repo_dir).glob("*.pkg.tar.zst"))
            if pkg_files:
                process = subprocess.run(
                    ["repo-add", "-f", self.db_name] + [str(f) for f in pkg_files],
                    check=True,
                    capture_output=True,
                    text=True
                )
            else:
                # Create empty database if no packages exist
                process = subprocess.run(
                    ["repo-add", "-f", self.db_name],
                    check=True,
                    capture_output=True,
                    text=True
                )

            print(f"Repository cleaned successfully. Removed {cleaned} old package versions.")
            self.logger.info(f"Repository cleaned. Removed {cleaned} old package versions.")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = self.log_error(cmd, f"Error cleaning repository",
                                     f"Command failed with return code {e.returncode}, "
                                     f"Stdout: {e.stdout}, Stderr: {e.stderr}")
            print(error_msg)
            return False
        except Exception as e:
            error_msg = self.log_error(cmd, f"Unexpected error cleaning repository",
                                     traceback.format_exc())
            print(error_msg)
            return False
        finally:
            os.chdir(current_dir)

    def show_status(self):
        """Show status of the repository"""
        cmd = "status"

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
            try:
                repo_size_result = subprocess.run(
                    ["du", "-sh", self.repo_dir],
                    capture_output=True,
                    text=True,
                    check=True
                )
                repo_size = repo_size_result.stdout.split()[0]
                print(f"Repository size: {repo_size}")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to get repository size: {e}")
                print("Repository size: Unknown")

            # Last update time
            try:
                db_path = Path(self.repo_dir) / self.db_name
                if db_path.exists():
                    last_update = datetime.datetime.fromtimestamp(db_path.stat().st_mtime)
                    print(f"Last database update: {last_update}")
                else:
                    print("Last database update: Never")
            except Exception as e:
                self.logger.warning(f"Failed to get last update time: {e}")
                print("Last database update: Unknown")

            # Disk space
            try:
                disk_result = subprocess.run(
                    ["df", "-h", self.repo_dir],
                    capture_output=True,
                    text=True,
                    check=True
                )
                disk_info = disk_result.stdout.splitlines()
                if len(disk_info) > 1:
                    disk_usage = disk_info[1].split()
                    print("Disk usage:")
                    print(f"  Filesystem: {disk_usage[0]}, Size: {disk_usage[1]}, "
                        f"Used: {disk_usage[2]}, Avail: {disk_usage[3]}, Use%: {disk_usage[4]}")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to get disk usage: {e}")
                print("Disk usage: Unknown")

            return True
        except Exception as e:
            error_msg = self.log_error(cmd, f"Error getting repository status",
                                     traceback.format_exc())
            print(error_msg)
            return False
        finally:
            os.chdir(current_dir)

    def receive_file(self, filename):
        """Receive a file through SSH"""
        cmd = f"receive {filename}"

        if not filename:
            error_msg = self.log_error(cmd, "No filename specified",
                                     "Command requires a filename")
            print(error_msg)
            print("Usage: receive <filename>")
            return False

        is_signature = filename.endswith('.sig')

        print(f"Ready to receive file: {filename}")
        print("Please paste the base64-encoded file content and end with a line containing only 'EOF'")
        print("Waiting for data...")

        # Create a temporary file to store the base64 data
        b64file_path = None
        output_path = None

        try:
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

            # Decode the base64 data to the actual file
            output_path = os.path.join(self.upload_dir, filename)

            try:
                with open(b64file_path, 'r') as b64file, open(output_path, 'wb') as outfile:
                    base64_data = b64file.read()
                    try:
                        binary_data = base64.b64decode(base64_data)
                    except base64.Error as e:
                        error_msg = self.log_error(cmd, f"Invalid base64 data",
                                               f"Base64 decode error: {e}")
                        print(error_msg)
                        return False

                    outfile.write(binary_data)
            except IOError as e:
                error_msg = self.log_error(cmd, f"File I/O error",
                                         f"Failed to write to {output_path}: {e}")
                print(error_msg)
                return False

            # Check if the file was created successfully
            if os.path.isfile(output_path):
                if is_signature:
                    print(f"Signature file received successfully: {filename}")
                else:
                    print(f"File received successfully: {filename}")

                # Get file size
                try:
                    file_size_result = subprocess.run(
                        ["du", "-h", output_path],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    file_size = file_size_result.stdout.split()[0]
                    print(f"Size: {file_size}")
                except subprocess.CalledProcessError as e:
                    self.logger.warning(f"Failed to get file size: {e}")
                    print("Size: Unknown")

                if not is_signature:
                    print(f"Use 'add {output_path}' to add it to the repository")

                self.logger.info(f"Successfully received file: {filename}")
                return True
            else:
                error_msg = self.log_error(cmd, "Failed to receive file",
                                         f"File {output_path} does not exist after decode operation")
                print(error_msg)
                return False
        except Exception as e:
            error_msg = self.log_error(cmd, f"Error receiving file",
                                     traceback.format_exc())
            print(error_msg)
            return False
        finally:
            # Clean up the temporary base64 file
            if b64file_path and os.path.exists(b64file_path):
                try:
                    os.unlink(b64file_path)
                except Exception as e:
                    self.logger.warning(f"Failed to clean up temporary file {b64file_path}: {e}")

    def send_file(self, filename):
        """Send a file through SSH"""
        cmd = f"send {filename}"

        if not filename:
            error_msg = self.log_error(cmd, "No filename specified",
                                     "Command requires a filename")
            print(error_msg)
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
            error_msg = self.log_error(cmd, f"File not found: {filename}",
                                     f"Checked paths: {repo_path}, {os.path.join(self.upload_dir, filename)}, {filename}")
            print(error_msg)
            print("The file must be in the repository, uploads directory, or you must specify a full path.")
            return False

        try:
            # Get file size
            file_size_result = subprocess.run(
                ["du", "-h", file_path],
                capture_output=True,
                text=True,
                check=True
            )
            file_size = file_size_result.stdout.split()[0]

            print(f"Sending file: {os.path.basename(file_path)}")
            print(f"Size: {file_size}")
            print("Base64 encoded data follows (copy everything between START and END markers):")
            print("-----START FILE DATA-----")

            # Read and encode the file
            try:
                with open(file_path, 'rb') as f:
                    encoded_data = base64.b64encode(f.read()).decode('utf-8')
                    print(encoded_data)
            except IOError as e:
                error_msg = self.log_error(cmd, f"File I/O error",
                                         f"Failed to read {file_path}: {e}")
                print(error_msg)
                return False

            print("-----END FILE DATA-----")
            print("")
            print("To save this file on your local machine:")
            print("1. Copy all the data between the START and END markers")
            print("2. Run this command in your local terminal:")
            print(f"   echo 'PASTE_DATA_HERE' | base64 -d > {os.path.basename(file_path)}")

            self.logger.info(f"Successfully sent file: {filename}")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = self.log_error(cmd, f"Error getting file size",
                                     f"Command du -h {file_path} failed: {e}")
            print(error_msg)
            return False
        except Exception as e:
            error_msg = self.log_error(cmd, f"Error sending file",
                                     traceback.format_exc())
            print(error_msg)
            return False

    def log_command(self, command):
        """Log command to history file"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with open(self.history_file, 'a') as f:
                f.write(f"{timestamp} - {command}\n")
        except Exception as e:
            self.logger.warning(f"Failed to log command to history file: {e}")

    def process_command(self, cmd, args):
        """Process a single command"""
        try:
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
            elif cmd == "errors":
                return self.show_recent_errors()
            elif cmd == "help":
                self.show_help()
                return True
            elif cmd in ["exit", "quit", "logout"]:
                print("Logging out...")
                return None  # Signal to exit
            else:
                error_msg = self.log_error(f"{cmd} {args}", f"Unknown command: {cmd}",
                                        "Command not recognized")
                print(error_msg)
                print("Type 'help' for a list of available commands")
                return False
        except Exception as e:
            error_msg = self.log_error(f"{cmd} {args}", f"Unexpected error processing command",
                                     traceback.format_exc())
            print(error_msg)
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
                error_msg = self.log_error("main_loop", f"Unexpected error in main loop",
                                        traceback.format_exc())
                print(error_msg)

    def process_stdin(self):
        """Process commands from standard input (non-interactive mode)"""
        for line in sys.stdin:
            try:
                line = line.strip()
                if not line or line == "exit":
                    continue

                parts = line.split(maxsplit=1)
                cmd = parts[0]
                args = parts[1] if len(parts) > 1 else ""

                self.process_command(cmd, args)
                print()  # Empty line after each command
            except Exception as e:
                error_msg = self.log_error("process_stdin", f"Unexpected error processing input",
                                        traceback.format_exc())
                print(error_msg)

    def _initialize_repo_database(self):
        """Initialize repository database if it doesn't exist"""
        db_path = os.path.join(self.repo_dir, self.db_name)
        if not os.path.exists(db_path):
            print(f"Initializing empty repository database at {db_path}...")
            current_dir = os.getcwd()
            try:
                os.chdir(self.repo_dir)
                process = subprocess.run(
                    ["repo-add", self.db_name],
                    check=True,
                    capture_output=True,
                    text=True
                )
                print("Repository database initialized successfully.")
                self.logger.info("Repository database initialized successfully")
            except subprocess.CalledProcessError as e:
                error_msg = self.log_error("initialize_repo", f"Error initializing repository database",
                                         f"Command: repo-add {self.db_name}, "
                                         f"Return code: {e.returncode}, "
                                         f"Stdout: {e.stdout}, Stderr: {e.stderr}")
                print(error_msg)
            except Exception as e:
                error_msg = self.log_error("initialize_repo", f"Unexpected error initializing repository",
                                         traceback.format_exc())
                print(error_msg)
            finally:
                os.chdir(current_dir)

if __name__ == "__main__":
    shell = PackageRepositoryShell()
    # Handle non-interactive mode
    if not sys.stdin.isatty():
        shell.process_stdin()
    else:
        shell.main_loop()
