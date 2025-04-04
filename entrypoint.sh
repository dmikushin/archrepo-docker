#!/bin/bash
set -e

# Allow pkguser to write to repository directory
mkdir -p /srv/repo
chown -R pkguser:pkguser /srv/repo
chmod -R 700 /srv/repo

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

# Ensure pkg_shell has proper permissions
echo "Setting up the custom shell..."
chmod +x /usr/local/bin/pkg_shell
chown root:root /usr/local/bin/pkg_shell

# Initialize directories and permissions
mkdir -p /home/pkguser/uploads
touch /home/pkguser/.pkg_shell_history
chown -R pkguser:pkguser /home/pkguser
chmod 700 /home/pkguser/uploads

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
