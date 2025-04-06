#!/bin/bash
set -e

# Repository configuration
REPO_DIR="/srv/repo/x86_64"
DB_NAME="repo.db.tar.zst"
UPLOAD_DIR="/home/pkguser/uploads"
HISTORY_FILE="/home/pkguser/.pkg_shell_history"
ERROR_LOG_FILE="/home/pkguser/.pkg_shell_errors.log"

# Export variables to environment so pkg_shell.py can access them
export REPO_DIR
export DB_NAME
export UPLOAD_DIR
export HISTORY_FILE
export ERROR_LOG_FILE

# Initialize directories and permissions
mkdir -p "$UPLOAD_DIR"
touch "$HISTORY_FILE"
touch "$ERROR_LOG_FILE"
chown -R pkguser:pkguser /home/pkguser
chmod 700 "$UPLOAD_DIR"

# Allow pkguser to write to repository directory
mkdir -p /srv
chown -R pkguser:pkguser /srv

# Create repository directory structure
mkdir -p "$REPO_DIR"
chown -R pkguser:pkguser "$REPO_DIR"

# Ensure pkg_shell has proper permissions
echo "Setting up the custom shell..."
chmod +x /usr/local/bin/pkg_shell
chown root:root /usr/local/bin/pkg_shell

# Initialize repository database if it doesn't exist
REPO_DB_PATH="$REPO_DIR/$DB_NAME"
if [ ! -f "$REPO_DB_PATH" ]; then
    echo "Initializing empty repository database..."
    pushd "$REPO_DIR"
    sudo -u pkguser repo-add "$DB_NAME"
    popd
    echo "Repository database initialized successfully."
fi

# Add our local repository to the existing pacman.conf
echo -e "\n# Add our local repository\n[repo]\nSigLevel = Optional TrustAll\nServer = file:///srv/repo/\$arch" >> /etc/pacman.conf

# TODO Deactivate existing repositories,
# which we no longer need to update

if [ "${TEST_MODE}" = "1" ]; then
    # Colors for better output
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m' # No Color

    # Display banner
    echo -e "${GREEN}=======================================================${NC}"
    echo -e "${GREEN}         ArchRepo API Test Suite Runner                ${NC}"
    echo -e "${GREEN}=======================================================${NC}"

    TEST_RESULT=0
    python ./test_direct_api.py || TEST_RESULT=$?

    # Check for errors in log files
    if [ -s /tmp/pkg_shell_test_errors.log ] || [ -s /tmp/pkg_shell_direct_test_errors.log ]; then
        echo -e "${YELLOW}Error logs contain entries:${NC}"
        echo -e "${YELLOW}Main test error log:${NC}"
        cat /tmp/pkg_shell_test_errors.log
        echo -e "${YELLOW}Direct test error log:${NC}"
        cat /tmp/pkg_shell_direct_test_errors.log
    fi

    # Check result
    if [ $TEST_RESULT -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        else
        echo -e "${RED}Tests failed!${NC}"
        exit 1
    fi

    echo -e "${GREEN}=======================================================${NC}"
    echo -e "${GREEN}         Test run complete                             ${NC}"
    echo -e "${GREEN}=======================================================${NC}"
else
    # Check if SSH key exists, if not create it
    SSH_KEY_FILE="/ssh-keys/id_ed25519"
    SSH_PUB_KEY_FILE="/ssh-keys/id_ed25519.pub"

    if [ ! -f "$SSH_PUB_KEY_FILE" ]; then
        echo "SSH key not found. Generating new ed25519 SSH key..."
        mkdir -p /ssh-keys
        ssh-keygen -t ed25519 -f "$SSH_KEY_FILE" -N "" -C "archrepo-docker"
        echo "New SSH key generated at $SSH_KEY_FILE"
        echo "Please use this key to perform administrative repository operations."
    fi

    # Add the public key to the authorized_keys file
    echo "Setting up SSH key for authentication..."
    cat "$SSH_PUB_KEY_FILE" > /home/pkguser/.ssh/authorized_keys
    chown pkguser:pkguser /home/pkguser/.ssh/authorized_keys
    chmod 600 /home/pkguser/.ssh/authorized_keys

    # Start nginx in background
    echo "Starting nginx..."
    mkdir -p /var/lib/nginx
    chown -R pkguser:pkguser /var/lib/nginx
    mkdir -p /var/log/nginx
    chown -R pkguser:pkguser /var/log/nginx
    sudo -u pkguser nginx

    # Start dropbear SSH server
    echo "Starting Dropbear SSH server..."
    sudo -u pkguser dropbear -R -E -p 2222

    # Keep container running
    echo "All services started."
    tail -f /dev/null
fi

