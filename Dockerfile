FROM archlinux:base

# Update system and install required packages
RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm \
    nginx \
    openssh \
    dropbear \
    rsync \
    vim \
    bash \
    sudo \
    git \
    base-devel \
    pacman-contrib

# Create repository directory structure
RUN mkdir -p /srv/repo/x86_64
WORKDIR /srv/repo

# Create a user for SSH access
RUN useradd -m -s /bin/bash pkguser && \
    mkdir -p /home/pkguser/.ssh && \
    touch /home/pkguser/.ssh/authorized_keys && \
    chown -R pkguser:pkguser /home/pkguser && \
    chmod 700 /home/pkguser/.ssh && \
    chmod 600 /home/pkguser/.ssh/authorized_keys

# Allow pkguser to write to repository directory
RUN chown -R pkguser:pkguser /srv/repo && \
    chmod -R 775 /srv/repo

# Configure NGINX
COPY nginx.conf /etc/nginx/nginx.conf

# Configure Dropbear SSH server
RUN mkdir -p /etc/dropbear && \
    dropbearkey -t ed25519 -f /etc/dropbear/dropbear_ed25519_host_key

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose ports
EXPOSE 80 2222

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
