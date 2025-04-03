#!/bin/bash
# pkg-shell.sh - Custom shell for pkguser that provides repository management functions

# Configuration
REPO_DIR="/srv/repo/x86_64"
DB_NAME="repo.db.tar.gz"
HISTORY_FILE="$HOME/.pkg_shell_history"
UPLOAD_DIR="$HOME/uploads"

# Create required directories
mkdir -p "$UPLOAD_DIR"
touch "$HISTORY_FILE"

# Function to display welcome message
function show_welcome {
    clear
    echo "================================================================"
    echo "                 ARCH REPOSITORY MANAGEMENT SHELL                "
    echo "================================================================"
    echo "Type 'help' to see available commands"
    echo
}

# Function to display help menu
function show_help {
    echo "Available commands:"
    echo "  add <package-file.pkg.tar.zst>  - Add a package to the repository"
    echo "  remove <package-name>           - Remove a package from the repository"
    echo "  list                            - List all packages in the repository"
    echo "  clean                           - Clean up old package versions"
    echo "  receive <filename>              - Receive a package file through the SSH connection"
    echo "  send <filename>                 - Send a file from the repository to the client"
    echo "  status                          - Show repository statistics"
    echo "  help                            - Show this help message"
    echo "  exit                            - Log out"
    echo
}

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
    local sig_file="${pkg_file}.zsig"

    # If the package is not in the repo dir, copy it there
    if [ ! -f "$REPO_DIR/$pkg_file" ]; then
        echo "Copying package to repository..."
        cp "$pkg_file" "$REPO_DIR/"
        pkg_file="$(basename "$pkg_file")"

        # Also copy signature file if it exists
        if [ -f "${1}.zsig" ]; then
            echo "Copying signature file to repository..."
            cp "${1}.zsig" "$REPO_DIR/${pkg_file}.zsig"
        elif [ -f "$UPLOAD_DIR/${pkg_file}.zsig" ]; then
            echo "Copying signature file from uploads to repository..."
            cp "$UPLOAD_DIR/${pkg_file}.zsig" "$REPO_DIR/${pkg_file}.zsig"
        fi
    fi

    # Update the repository database
    echo "Updating repository database..."
    cd "$REPO_DIR"
    repo-add "$DB_NAME" "$pkg_file"
    echo "Package added successfully."
}

# Function to remove a package
function remove_package {
    if [ -z "$1" ]; then
        echo "Error: No package specified"
        echo "Usage: remove <package-name>"
        return 1
    fi

    cd "$REPO_DIR"
    # Check if the package exists in the database
    if ! pacman -Sl custom | grep -q "$1"; then
        echo "Error: Package not found in repository: $1"
        return 1
    fi

    # Remove the package from the database
    echo "Removing package from database..."
    repo-remove "$DB_NAME" "$1"

    # Remove the package file(s) and signatures
    echo "Removing package files and signatures..."
    rm -fv "$1"-*.pkg.tar.zst
    rm -fv "$1"-*.pkg.tar.zst.zsig
    echo "Package removed successfully."
}

# Function to list packages
function list_packages {
    echo "Packages in repository:"
    echo "----------------------"
    cd "$REPO_DIR"
    pacman -Sl custom

    # Count packages
    local count=$(pacman -Sl custom | wc -l)
    echo "----------------------"
    echo "Total packages: $count"
}

# Function to clean repository
function clean_repo {
    echo "Cleaning repository..."
    cd "$REPO_DIR"

    local cleaned=0
    # Find all packages
    for pkg in *.pkg.tar.zst; do
        if [ -f "$pkg" ]; then
            pkg_name=$(echo "$pkg" | sed 's/-[0-9].*$//')

            # Find all versions of this package
            versions=$(find . -name "${pkg_name}-*.pkg.tar.zst" | sort -V)
            count=$(echo "$versions" | wc -l)

            # If there are multiple versions, keep only the latest
            if [ "$count" -gt 1 ]; then
                # Remove all but the latest version
                echo "Cleaning old versions of $pkg_name..."
                echo "$versions" | head -n -1 | xargs -I{} sh -c 'rm -v "{}" && rm -fv "{}".zsig'
                cleaned=$((cleaned + count - 1))
            fi
        fi
    done

    # Rebuild the database
    echo "Rebuilding repository database..."
    repo-add -f "$DB_NAME" *.pkg.tar.zst
    echo "Repository cleaned successfully. Removed $cleaned old package versions."
}

# Function to show status of the repository
function show_status {
    echo "Repository Status:"
    echo "-----------------"
    cd "$REPO_DIR"

    # Count packages
    local pkg_count=$(ls -1 *.pkg.tar.zst 2>/dev/null | wc -l)
    echo "Total packages: $pkg_count"

    # Count signatures
    local sig_count=$(ls -1 *.pkg.tar.zst.zsig 2>/dev/null | wc -l)
    echo "Signed packages: $sig_count"

    # Repository size
    local repo_size=$(du -sh "$REPO_DIR" | cut -f1)
    echo "Repository size: $repo_size"

    # Last update time
    local last_update=$(stat -c %y "$DB_NAME" 2>/dev/null || echo "Never")
    echo "Last database update: $last_update"

    # Disk space
    local disk_usage=$(df -h "$REPO_DIR" | tail -n 1)
    echo "Disk usage:"
    echo "  $(echo "$disk_usage" | awk '{print "Filesystem: " $1 ", Size: " $2 ", Used: " $3 ", Avail: " $4 ", Use%: " $5}')"
}

# Function to receive a file through SSH
function receive_file {
    if [ -z "$1" ]; then
        echo "Error: No filename specified"
        echo "Usage: receive <filename>"
        return 1
    fi

    local filename="$1"
    local is_signature=false

    # Check if this is a signature file
    if [[ "$filename" == *.zsig ]]; then
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
    base64 -d "$b64file" > "$UPLOAD_DIR/$filename"
    rm "$b64file"

    # Check if the file was created successfully
    if [ -f "$UPLOAD_DIR/$filename" ]; then
        if $is_signature; then
            echo "Signature file received successfully: $filename"
        else
            echo "File received successfully: $filename"
        fi
        echo "Size: $(du -h "$UPLOAD_DIR/$filename" | cut -f1)"

        if ! $is_signature; then
            echo "Use 'add $UPLOAD_DIR/$filename' to add it to the repository"
        fi
        return 0
    else
        echo "Error: Failed to receive file."
        return 1
    fi
}

# Function to send a file through SSH
function send_file {
    if [ -z "$1" ]; then
        echo "Error: No filename specified"
        echo "Usage: send <filename>"
        return 1
    fi

    local file_path=""

    # Check if the file exists in the repository
    if [ -f "$REPO_DIR/$1" ]; then
        file_path="$REPO_DIR/$1"
    # Check if it exists in the uploads directory
    elif [ -f "$UPLOAD_DIR/$1" ]; then
        file_path="$UPLOAD_DIR/$1"
    # Check if it's a full path
    elif [ -f "$1" ]; then
        file_path="$1"
    else
        echo "Error: File not found: $1"
        echo "The file must be in the repository, uploads directory, or you must specify a full path."
        return 1
    fi

    echo "Sending file: $(basename "$file_path")"
    echo "Size: $(du -h "$file_path" | cut -f1)"
    echo "Base64 encoded data follows (copy everything between START and END markers):"
    echo "-----START FILE DATA-----"
    base64 "$file_path"
    echo "-----END FILE DATA-----"
    echo ""
    echo "To save this file on your local machine:"
    echo "1. Copy all the data between the START and END markers"
    echo "2. Run this command in your local terminal:"
    echo "   echo 'PASTE_DATA_HERE' | base64 -d > $(basename "$file_path")"
}

# Function to log command to history
function log_command {
    echo "$(date +'%Y-%m-%d %H:%M:%S') - $1" >> "$HISTORY_FILE"
}

# Main interactive loop
show_welcome

while true; do
    # Print prompt
    echo -n "pkgrepo> "
    read -r cmd args

    # Log command (except exit)
    if [ "$cmd" != "exit" ]; then
        log_command "$cmd $args"
    fi

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
        send)
            send_file "$args"
            ;;
        help)
            show_help
            ;;
        exit|quit|logout)
            echo "Logging out..."
            exit 0
            ;;
        "")
            # Do nothing on empty command
            ;;
        *)
            echo "Unknown command: $cmd"
            echo "Type 'help' for a list of available commands"
            ;;
    esac

    echo
done
