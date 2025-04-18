#!/usr/bin/env python3
"""
archrepo.py - Python API for managing an Arch Linux package repository
"""

import argparse
import base64
import os
import subprocess
import sys
from typing import List, Dict, Optional, Tuple, Union
import re
import hashlib


class ArchRepoClient:
    def __init__(self, host: str):
        """
        Initialize a new ArchRepoClient instance.

        Args:
            host: SSH host
        """
        self.host = host

    def _run_ssh_interactive(self, commands: List[str]) -> Tuple[int, str, str]:
        """
        Execute commands in the custom shell via SSH.

        This method handles the interactive shell by sending commands and then sending "exit"
        to properly terminate the session.

        Args:
            commands: List of commands to execute

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        # Prepare the complete input for the SSH session
        # Each command followed by a newline, and ending with 'exit'
        input_data = "\n".join(commands + ["exit"]) + "\n"

        ssh_args = [
            "ssh",
            self.host
        ]

        process = subprocess.Popen(
            ssh_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        stdout, stderr = process.communicate(input=input_data)
        return process.returncode, stdout, stderr

    def _encode_and_send_file(self, commands: List[str], file_path: str, filename: str) -> List[str]:
        """
        Encode a file and add commands to send it to the server.

        Args:
            commands: The command list to append to
            file_path: Path to the file to encode
            filename: Name to use for the file on the server

        Returns:
            Updated commands list
        """
        # Base64 encode the file
        with open(file_path, 'rb') as file:
            file_data = file.read()

        # Calculate SHA-512 hash
        file_hash = hashlib.sha512(file_data).hexdigest()

        encoded_data = base64.b64encode(file_data).decode('utf-8')

        # Add receive command with hash
        commands.append(f"receive {filename} {file_hash}")

        # Add the base64 data in chunks to avoid line length issues
        chunk_size = 76  # Standard base64 line length
        for i in range(0, len(encoded_data), chunk_size):
            commands.append(encoded_data[i:i+chunk_size])

        # End of file marker
        commands.append("EOF")

        return commands

    def publish_package(self, package_path: str, no_signing: bool = False) -> Tuple[bool, str]:
        """
        Publish a package to the repository (upload and add in a single operation).
        Also uploads the .sig signature file if it exists and no_signing is False.

        Args:
            package_path: Path to the package file
            no_signing: If True, signature check will be skipped

        Returns:
            Tuple of (success, message)
        """
        # Check if package file exists
        if not os.path.isfile(package_path):
            return False, f"Package file not found: {package_path}"

        # Get just the filename without path
        filename = os.path.basename(package_path)

        # Check for signature file
        signature_path = f"{package_path}.sig"
        signature_exists = os.path.isfile(signature_path)

        if not signature_exists and not no_signing:
            return False, f"Signature file not found: {signature_path}. Use --no-signing to skip signature check."

        try:
            # Prepare the commands list
            commands = []

            # Send the package file
            commands = self._encode_and_send_file(commands, package_path, filename)

            # If we have a signature and signing is required, send it too
            if signature_exists and not no_signing:
                signature_filename = f"{filename}.sig"
                commands = self._encode_and_send_file(commands, signature_path, signature_filename)

            # Add the package to the repo
            commands.append(f"add {filename}")

            # Run the commands interactively
            return_code, stdout, stderr = self._run_ssh_interactive(commands)

            if return_code != 0:
                return False, f"Operation failed: {stderr}"

            # Success messages to look for
            pkg_received = "File received successfully" in stdout
            hash_verified = "SHA-512 hash verification: SUCCESS" in stdout or "SHA-512 hash verification" not in stdout
            sig_received = True  # Assume true initially

            # If we sent a signature, check it was received
            if signature_exists and not no_signing:
                sig_received = "Signature file received successfully" in stdout

            pkg_added = "Package added successfully" in stdout

            if not hash_verified:
                return False, "Package upload failed: SHA-512 hash verification failed."
            elif pkg_received and sig_received and pkg_added:
                return True, "Package and signature uploaded and added to repository successfully."
            elif pkg_received and sig_received:
                return False, "Package and signature uploaded but failed to add to repository."
            elif pkg_received:
                return False, "Package uploaded but signature transfer failed or package addition failed."
            else:
                return False, "Upload failed: Files not received successfully."

        except Exception as e:
            return False, f"Error during operation: {str(e)}"

    def remove_package(self, package_name: str) -> Tuple[bool, str]:
        """
        Remove a package from the repository.

        Args:
            package_name: Name of the package (without version info)

        Returns:
            Tuple of (success, message)
        """
        return_code, stdout, stderr = self._run_ssh_interactive([f"remove {package_name}"])

        if return_code != 0:
            return False, f"Failed to remove package: {stderr}"

        if "Package removed successfully" in stdout:
            return True, "Package removed from repository successfully."
        else:
            return False, "Failed to remove package from repository."

    def list_packages(self) -> Tuple[bool, Union[List[Dict[str, str]], str]]:
        """
        List all packages in the repository.

        Returns:
            Tuple of (success, packages or error message)
            If successful, packages is a list of dictionaries with keys:
                - name: Package name
                - version: Package version
                - description: Package description
        """
        return_code, stdout, stderr = self._run_ssh_interactive(["list"])

        if return_code != 0:
            return False, f"Failed to list packages: {stderr}"

        packages = []
        for line in stdout.splitlines():
            # Parse the output of pacman -Sl custom
            if line.startswith("custom "):
                parts = line.split()
                if len(parts) >= 4:
                    # Format is typically: custom package_name version description
                    repo, name, version = parts[0:3]
                    description = " ".join(parts[3:])
                    packages.append({
                        "name": name,
                        "version": version,
                        "description": description
                    })

        return True, packages

    def clean_repository(self) -> Tuple[bool, str]:
        """
        Clean the repository by removing old package versions.

        Returns:
            Tuple of (success, message)
        """
        return_code, stdout, stderr = self._run_ssh_interactive(["clean"])

        if return_code != 0:
            return False, f"Failed to clean repository: {stderr}"

        if "Repository cleaned successfully" in stdout:
            # Extract the number of removed packages if available
            match = re.search(r"Removed (\d+) old package versions", stdout)
            if match:
                count = match.group(1)
                return True, f"Repository cleaned successfully. Removed {count} old package versions."
            return True, "Repository cleaned successfully."
        else:
            return False, "Failed to clean repository."

    def get_status(self) -> Tuple[bool, Union[Dict[str, str], str]]:
        """
        Get repository status information.

        Returns:
            Tuple of (success, status_info or error message)
        """
        return_code, stdout, stderr = self._run_ssh_interactive(["status"])

        if return_code != 0:
            return False, f"Failed to get repository status: {stderr}"

        status_info = {}

        # Parse the output to extract status information
        for line in stdout.splitlines():
            if ":" in line:
                key, value = [x.strip() for x in line.split(":", 1)]
                status_info[key] = value

        return True, status_info

def main():
    """
    Command-line interface for ArchRepoClient.
    """
    parser = argparse.ArgumentParser(description="ArchRepo Client API")

    parser.add_argument("-H", "--host", help="SSH host as specified in ~/.ssh/config")

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Publish command (upload and add)
    publish_parser = subparsers.add_parser("publish", help="Publish a package (upload and add to repository)")
    publish_parser.add_argument("package_file", help="Package file to publish")
    publish_parser.add_argument("--no-signing", action="store_true", help="Skip signature check for this package")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a package")
    remove_parser.add_argument("package_name", help="Package name to remove")

    # List command
    subparsers.add_parser("list", help="List all packages")

    # Clean command
    subparsers.add_parser("clean", help="Clean repository")

    # Status command
    subparsers.add_parser("status", help="Show repository status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        # Create client instance
        client = ArchRepoClient(host=args.host)

        # Execute requested command
        if args.command == "publish":
            no_signing = getattr(args, "no_signing", False)
            success, message = client.publish_package(args.package_file, no_signing=no_signing)
            print(message)
            return 0 if success else 1

        elif args.command == "remove":
            success, message = client.remove_package(args.package_name)
            print(message)
            return 0 if success else 1

        elif args.command == "list":
            success, result = client.list_packages()
            if success:
                print("Packages in repository:")
                print("----------------------")
                for pkg in result:
                    print(f"{pkg['name']} {pkg['version']} - {pkg['description']}")
                print("----------------------")
                print(f"Total packages: {len(result)}")
                return 0
            else:
                print(f"Error: {result}")
                return 1

        elif args.command == "clean":
            success, message = client.clean_repository()
            print(message)
            return 0 if success else 1

        elif args.command == "status":
            success, result = client.get_status()
            if success:
                print("Repository Status:")
                print("-----------------")
                for key, value in result.items():
                    print(f"{key}: {value}")
                return 0
            else:
                print(f"Error: {result}")
                return 1

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
