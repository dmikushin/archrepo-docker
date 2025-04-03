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

    def publish_package(self, package_path: str) -> Tuple[bool, str]:
        """
        Publish a package to the repository (upload and add in a single operation).

        Args:
            package_path: Path to the package file

        Returns:
            Tuple of (success, message)
        """
        # Check if package file exists
        if not os.path.isfile(package_path):
            return False, f"Package file not found: {package_path}"

        # Get just the filename without path
        filename = os.path.basename(package_path)

        try:
            # Base64 encode the package file
            with open(package_path, 'rb') as file:
                file_data = file.read()
            encoded_data = base64.b64encode(file_data).decode('utf-8')

            # Prepare the commands list
            commands = [f"receive {filename}"]

            # Add the base64 data in chunks to avoid line length issues
            chunk_size = 76  # Standard base64 line length
            for i in range(0, len(encoded_data), chunk_size):
                commands.append(encoded_data[i:i+chunk_size])

            # End of file marker
            commands.append("EOF")

            # Add the package to the repo
            commands.append(f"add /home/pkguser/uploads/{filename}")

            # Run the commands interactively
            return_code, stdout, stderr = self._run_ssh_interactive(commands)

            if return_code != 0:
                return False, f"Operation failed: {stderr}"

            if "File received successfully" in stdout and "Package added successfully" in stdout:
                return True, "Package uploaded and added to repository successfully."
            elif "File received successfully" in stdout:
                return False, "Package uploaded but failed to add to repository."
            else:
                return False, "Upload failed: File not received successfully."

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

    def download_package(self, package_name: str, output_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Download a package from the repository.

        Args:
            package_name: Name of the package file to download
            output_path: Local path to save the file (default: current directory with same filename)

        Returns:
            Tuple of (success, message or output path)
        """
        if not output_path:
            output_path = os.path.basename(package_name)

        return_code, stdout, stderr = self._run_ssh_interactive([f"send {package_name}"])

        if return_code != 0:
            return False, f"Failed to download package: {stderr}"

        # Extract the base64 data between the START and END markers
        match = re.search(r"-----START FILE DATA-----\n(.*?)-----END FILE DATA-----",
                         stdout, re.DOTALL)

        if not match:
            return False, "Failed to extract file data from response."

        encoded_data = match.group(1).strip()

        try:
            # Decode and save the file
            with open(output_path, 'wb') as file:
                file.write(base64.b64decode(encoded_data))
            return True, f"Package downloaded successfully to {output_path}"
        except Exception as e:
            return False, f"Error saving package file: {str(e)}"


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

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a package")
    remove_parser.add_argument("package_name", help="Package name to remove")

    # List command
    subparsers.add_parser("list", help="List all packages")

    # Clean command
    subparsers.add_parser("clean", help="Clean repository")

    # Status command
    subparsers.add_parser("status", help="Show repository status")

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a package")
    download_parser.add_argument("package_name", help="Package file to download")
    download_parser.add_argument("-o", "--output", help="Output file path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        # Create client instance
        client = ArchRepoClient(host=args.host)

        # Execute requested command
        if args.command == "publish":
            success, message = client.publish_package(args.package_file)
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

        elif args.command == "download":
            success, message = client.download_package(args.package_name, args.output)
            print(message)
            return 0 if success else 1

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
