#!/bin/bash
set -e

# Initialize repository if it's empty
if [ ! -f /srv/repo/x86_64/repo.db.tar.gz ]; then
    echo "Initializing empty repository..."
    mkdir -p /srv/repo/x86_64
    repo-add /srv/repo/x86_64/repo.db.tar.gz
fi

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
nginx

# Start dropbear SSH server
echo "Starting Dropbear SSH server..."
dropbear -R -E -p 2222

# Keep container running
echo "All services started."
tail -f /dev/null
