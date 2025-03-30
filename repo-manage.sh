#!/bin/bash
# repo-manage.sh - A script to manage the Arch repository

# Configuration
REPO_DIR="/srv/repo/x86_64"
DB_NAME="repo.db.tar.gz"

function show_help {
    echo "Arch Package Repository Management Script"
    echo "Usage:"
    echo "  $0 add <package-file>     - Add a package to the repository"
    echo "  $0 remove <package-name>  - Remove a package from the repository"
    echo "  $0 list                   - List all packages in the repository"
    echo "  $0 clean                  - Clean up old package versions"
    echo "  $0 help                   - Show this help message"
}

function add_package {
    if [ ! -f "$1" ]; then
        echo "Error: Package file not found: $1"
        exit 1
    fi
    
    # Copy the package to the repository directory
    cp "$1" "$REPO_DIR/"
    
    # Update the repository database
    cd "$REPO_DIR"
    repo-add "$DB_NAME" "$(basename "$1")"
    echo "Package added successfully."
}

function remove_package {
    cd "$REPO_DIR"
    # Remove the package from the database
    repo-remove "$DB_NAME" "$1"
    
    # Remove the package file(s)
    rm -f "$1"-*.pkg.tar.zst
    echo "Package removed successfully."
}

function list_packages {
    echo "Packages in repository:"
    cd "$REPO_DIR"
    pacman -Sl custom
}

function clean_repo {
    echo "Cleaning repository..."
    cd "$REPO_DIR"
    
    # Find all packages
    for pkg in *.pkg.tar.zst; do
        if [ -f "$pkg" ]; then
            pkg_name=$(echo "$pkg" | sed 's/-[0-9].*$//')
            pkg_ver=$(echo "$pkg" | sed -n 's/.*-\([0-9].*\)-x86_64.pkg.tar.zst/\1/p')
            
            # Find all versions of this package
            versions=$(find . -name "${pkg_name}-*.pkg.tar.zst" | sort -V)
            count=$(echo "$versions" | wc -l)
            
            # If there are multiple versions, keep only the latest
            if [ "$count" -gt 1 ]; then
                # Remove all but the latest version
                echo "$versions" | head -n -1 | xargs rm -v
            fi
        fi
    done
    
    # Rebuild the database
    repo-add -f "$DB_NAME" *.pkg.tar.zst
    echo "Repository cleaned successfully."
}

# Main script logic
case "$1" in
    add)
        add_package "$2"
        ;;
    remove)
        remove_package "$2"
        ;;
    list)
        list_packages
        ;;
    clean)
        clean_repo
        ;;
    help|*)
        show_help
        ;;
esac
