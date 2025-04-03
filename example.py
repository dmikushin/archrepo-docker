#!/usr/bin/env python3
"""
Example usage of the ArchRepo API
"""

from archrepo import ArchRepoClient

def main():
    # Initialize the client with your server details
    client = ArchRepoClient(
        host="localhost",
        port="2222",
        user="pkguser",
        key_path="./ssh-keys/id_ed25519"
    )

    # Example 1: Publish a package (upload and add to repository in one step)
    success, message = client.publish_package("my-package-1.0-1-x86_64.pkg.tar.zst")
    print(f"Publish result: {message}")

    # Example 2: List packages in the repository
    success, packages = client.list_packages()
    if success:
        print("\nPackages in repository:")
        for pkg in packages:
            print(f"- {pkg['name']} ({pkg['version']}): {pkg['description']}")

    # Example 3: Get repository status
    success, status = client.get_status()
    if success:
        print("\nRepository status:")
        for key, value in status.items():
            print(f"- {key}: {value}")

    # Example 4: Clean the repository
    success, message = client.clean_repository()
    print(f"\nRepository cleanup: {message}")

    # Example 5: Download a package
    success, message = client.download_package(
        "my-package-1.0-1-x86_64.pkg.tar.zst",
        output_path="./downloaded-package.pkg.tar.zst"
    )
    print(f"\nDownload result: {message}")

    # Example 6: Remove a package
    success, message = client.remove_package("my-package")
    print(f"\nRemove result: {message}")

if __name__ == "__main__":
    main()
