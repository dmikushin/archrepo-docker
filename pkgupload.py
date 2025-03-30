#!/usr/bin/env python3
"""
pkgupload.py - Client script to upload packages to the Arch Linux repository
"""

import argparse
import base64
import os
import subprocess
import sys
import tempfile


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Package Upload Utility")

    parser.add_argument("package_file", nargs="?", help="Package file to upload")

    parser.add_argument("-H", "--host",
                        default=os.environ.get("SSH_HOST", "localhost"),
                        help="SSH host (default: localhost or SSH_HOST env var)")

    parser.add_argument("-p", "--port",
                        default=os.environ.get("SSH_PORT", "2222"),
                        help="SSH port (default: 2222 or SSH_PORT env var)")

    parser.add_argument("-k", "--key",
                        default=os.environ.get("SSH_KEY", "./ssh-keys/id_ed25519"),
                        help="SSH key file (default: ./ssh-keys/id_ed25519 or SSH_KEY env var)")

    parser.add_argument("-u", "--user",
                        default=os.environ.get("SSH_USER", "pkguser"),
                        help="SSH username (default: pkguser or SSH_USER env var)")

    parser.add_argument("-a", "--add", action="store_true",
                        help="Automatically add package to repository after upload")

    args = parser.parse_args()

    # Check if package file was specified
    if not args.package_file:
        parser.print_help()
        sys.exit(1)

    return args


def check_file_exists(file_path):
    """Check if the file exists and is readable"""
    if not os.path.isfile(file_path):
        print(f"Error: Package file not found: {file_path}")
        sys.exit(1)

    if not os.access(file_path, os.R_OK):
        print(f"Error: Package file is not readable: {file_path}")
        sys.exit(1)


def encode_file(file_path):
    """Base64 encode the file contents"""
    try:
        with open(file_path, 'rb') as file:
            file_data = file.read()
        return base64.b64encode(file_data).decode('utf-8')
    except Exception as e:
        print(f"Error encoding file: {e}")
        sys.exit(1)


def create_upload_script(filename, encoded_data, auto_add=False):
    """Create a temporary script file with commands to upload and optionally add the package"""
    try:
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)

        # Add receive command
        temp_file.write(f"receive {filename}\n")

        # Add base64 data in chunks to avoid line length issues
        chunk_size = 76  # Standard base64 line length
        for i in range(0, len(encoded_data), chunk_size):
            temp_file.write(encoded_data[i:i+chunk_size] + "\n")

        # End of file marker
        temp_file.write("EOF\n")

        # Add command to add the package if requested
        if auto_add:
            temp_file.write(f"add /home/pkguser/uploads/{filename}\n")

        # Add exit command
        temp_file.write("exit\n")

        temp_file.close()
        return temp_file.name
    except Exception as e:
        print(f"Error creating upload script: {e}")
        sys.exit(1)


def upload_package(script_path, ssh_args):
    """Execute the script via SSH to upload the package"""
    try:
        print("Uploading package...")
        print(f"This may take a while depending on the package size...")

        with open(script_path, 'r') as script_file:
            ssh_process = subprocess.Popen(
                ssh_args,
                stdin=script_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            stdout, stderr = ssh_process.communicate()

            print(stdout)
            if stderr:
                print(f"SSH stderr: {stderr}", file=sys.stderr)

            return ssh_process.returncode
    except Exception as e:
        print(f"Error executing SSH command: {e}")
        sys.exit(1)


def main():
    """Main function to upload a package"""
    args = parse_arguments()

    # Check if package file exists
    check_file_exists(args.package_file)

    # Get the filename without path
    filename = os.path.basename(args.package_file)

    # Check if SSH key exists
    check_file_exists(args.key)

    # Base64 encode the package file
    print(f"Encoding package file: {args.package_file}")
    encoded_data = encode_file(args.package_file)

    # Create temporary script file
    script_path = create_upload_script(filename, encoded_data, args.add)

    try:
        # Prepare SSH command arguments
        ssh_args = [
            "ssh",
            "-i", args.key,
            "-p", args.port,
            f"{args.user}@{args.host}"
        ]

        print(f"Connecting to {args.user}@{args.host}:{args.port}...")

        # Execute the upload
        return_code = upload_package(script_path, ssh_args)

        # Check if upload was successful
        if return_code == 0:
            print("Package uploaded successfully.")
            if args.add:
                print("Package has been added to the repository.")
            else:
                print("To add the package to the repository, connect to the SSH interface and use:")
                print(f"  add /home/pkguser/uploads/{filename}")
            return 0
        else:
            print("Error: Package upload failed.")
            return 1
    finally:
        # Clean up the temporary script file
        if os.path.exists(script_path):
            os.unlink(script_path)


if __name__ == "__main__":
    sys.exit(main())
