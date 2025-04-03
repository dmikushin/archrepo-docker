#!/bin/bash
# mock_pkg_shell.sh - A testing variant of pkg-shell.sh that works without network

# Override configuration for testing
if [ -z "$REPO_DIR" ]; then
    REPO_DIR="/tmp/test_repo/x86_64"
fi

if [ -z "$DB_NAME" ]; then
    DB_NAME="repo.db.tar.gz"
fi

if [ -z "$UPLOAD_DIR" ]; then
    UPLOAD_DIR="/tmp/uploads"
fi

HISTORY_FILE="/tmp/pkg_shell_test_history"

# Create required directories
mkdir -p "$REPO_DIR"
mkdir -p "$UPLOAD_DIR"
touch "$HISTORY_FILE"

# Initialize repo if needed
if [ ! -f "$REPO_DIR/$DB_NAME" ]; then
    echo "Initializing test repository..."
    repo-add "$REPO_DIR/$DB_NAME"
fi

# Main functions from pkg-shell.sh but modified for testing

# Function to add a package
function add_package {
    if [ -z "$1" ]; then
        echo "Error: No package specified"
        echo "Usage: add <package-file.pkg.tar.zst>"
        return 1
    fi

    if [ ! -f "$1" ] && [ ! -f "$REPO_DIR/$1" ]; then
        echo "Error: Package file not found: $1"
        echo "Note: Package must be in the current directory or already in the repository"
        return 1
    fi

    local pkg_file="$1"
    local sig_file="${pkg_file}.sig"

    # If the package is not in the repo dir, copy it there
    if [ ! -f "$REPO_DIR/$(basename "$pkg_file")" ]; then
        echo "Copying package to repository..."
        cp "$pkg_file" "$REPO_DIR/"
        pkg_file="$(basename "$pkg_file")"

        # Also copy signature file if it exists
        if [ -f "${1}.sig" ]; then
            echo "Copying signature file to repository..."
            cp "${1}.sig" "$REPO_DIR/${pkg_file}.sig"
        elif [ -f "$UPLOAD_DIR/${pkg_file}.sig" ]; then
            echo "Copying signature file from uploads to repository..."
            cp "$UPLOAD_DIR/${pkg_file}.sig" "$REPO_DIR/${pkg_file}.sig"
        fi
    else
        # Make sure we're using the basename for repo operations
        pkg_file="$(basename "$pkg_file")"
    fi

    # Update the repository database
    echo "Updating repository database..."
    cd "$REPO_DIR"
    repo-add "$DB_NAME" "$pkg_file"
    echo "Package added successfully."
    return 0
}

# Function to remove a package
function remove_package {
    if [ -z "$1" ]; then
        echo "Error: No package specified"
        echo "Usage: remove <package-name>"
        return 1
    fi

    cd "$REPO_DIR"

    # For testing, just attempt to remove without checking if it exists
    echo "Removing package from database..."
    repo-remove "$DB_NAME" "$1"

    # Remove the package file(s) and signatures
    echo "Removing package files and signatures..."
    rm -fv "$1"-*.pkg.tar.zst
    rm -fv "$1"-*.pkg.tar.zst.sig
    echo "Package removed successfully."
    return 0
}

# Function to list packages (modified for testing)
function list_packages {
    echo "Packages in repository:"
    echo "----------------------"
    cd "$REPO_DIR"

    # For testing, we'll simulate the pacman -Sl output
    for pkg in *.pkg.tar.zst; do
        if [ -f "$pkg" ]; then
            # Extract package name and version
            pkg_name=$(echo "$pkg" | sed -E 's/^([^-]+(-[^-]+)*)-.*/\1/')
            pkg_ver=$(echo "$pkg" | sed -E 's/^[^-]+((-[^-]+)*)-([^-]+)-([^-]+)-([^.]+).*/\3-\4/')

            echo "custom $pkg_name $pkg_ver This is a test package description"
        fi
    done

    # Count packages
    local count=$(ls -1 *.pkg.tar.zst 2>/dev/null | wc -l)
    echo "----------------------"
    echo "Total packages: $count"
    return 0
}

# Function to clean repository (simplified for testing)
function clean_repo {
    echo "Cleaning repository..."
    cd "$REPO_DIR"

    local cleaned=0
    # Find all packages
    for pkg_name in $(ls -1 *.pkg.tar.zst | sed -E 's/^([^-]+(-[^-]+)*)-.*/\1/' | uniq); do
        # Find all versions of this package
        versions=$(ls -1 ${pkg_name}-*.pkg.tar.zst 2>/dev/null | sort -V)
        count=$(echo "$versions" | wc -l)

        # If there are multiple versions, keep only the latest
        if [ "$count" -gt 1 ]; then
            # Remove all but the latest version
            echo "Cleaning old versions of $pkg_name..."
            echo "$versions" | head -n -1 | xargs -I{} sh -c 'rm -v "{}" && rm -fv "{}".sig'
            cleaned=$((cleaned + count - 1))
        fi
    done

    # Rebuild the database
    echo "Rebuilding repository database..."
    repo-add -f "$DB_NAME" *.pkg.tar.zst 2>/dev/null
    echo "Repository cleaned successfully. Removed $cleaned old package versions."
    return 0
}

# Function to show status (simplified for testing)
function show_status {
    echo "Repository Status:"
    echo "-----------------"
    cd "$REPO_DIR"

    # Count packages
    local pkg_count=$(ls -1 *.pkg.tar.zst 2>/dev/null | wc -l)
    echo "Total packages: $pkg_count"

    # Count signatures
    local sig_count=$(ls -1 *.pkg.tar.zst.sig 2>/dev/null | wc -l)
    echo "Signed packages: $sig_count"

    # Repository size
    local repo_size=$(du -sh "$REPO_DIR" 2>/dev/null | cut -f1)
    echo "Repository size: $repo_size"

    # Last update time
    local last_update=$(stat -c %y "$DB_NAME" 2>/dev/null || echo "Never")
    echo "Last database update: $last_update"

    return 0
}

# Function to receive a file (simplified for testing)
function receive_file {
    if [ -z "$1" ]; then
        echo "Error: No filename specified"
        echo "Usage: receive <filename>"
        return 1
    fi

    local filename="$1"
    local is_signature=false

    # Check if this is a signature file
    if [[ "$filename" == *.sig ]]; then
        is_signature=true
    fi

    echo "Ready to receive file: $filename"
    echo "Please paste the base64-encoded file content and end with a line containing only 'EOF'"
    echo "Waiting for data..."

    # Create a temporary file to store the base64 data
    local b64file=$(mktemp)

    # Read input until we get the EOF marker
    while IFS= read -r line; do
        if [ "$line" = "EOF" ]; then
            break
        fi
        echo "$line" >> "$b64file"
    done

    # Decode the base64 data to the actual file
    base64 -d "$b64file" > "$UPLOAD_DIR/$filename" 2>/dev/null || true
    rm "$b64file"

    # For testing, we'll just assume it worked
    if $is_signature; then
        echo "Signature file received successfully: $filename"
    else
        echo "File received successfully: $filename"
    fi
    echo "Size: $(du -h "$UPLOAD_DIR/$filename" 2>/dev/null | cut -f1 || echo "0")"

    if ! $is_signature; then
        echo "Use 'add $UPLOAD_DIR/$filename' to add it to the repository"
    fi
    return 0
}

# Read each line of input and process commands
while read -r line; do
    if [ -z "$line" ]; then
        continue
    fi

    if [ "$line" = "exit" ]; then
        echo "Exiting mock shell..."
        break
    fi

    # Extract command and arguments
    cmd=$(echo "$line" | awk '{print $1}')
    args=$(echo "$line" | cut -d' ' -f2-)

    # Process command
    case "$cmd" in
        add)
            add_package "$args"
            ;;
        remove)
            remove_package "$args"
            ;;
        list)
            list_packages
            ;;
        clean)
            clean_repo
            ;;
        status)
            show_status
            ;;
        receive)
            receive_file "$args"
            ;;
        help)
            echo "Mock shell for testing, supports: add, remove, list, clean, status, receive"
            ;;
        *)
            echo "Unknown command: $cmd"
            ;;
    esac

    echo ""  # Add an empty line after each command
done
