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
    pacman-contrib \
    python

# Create custom shell script for repository management
COPY pkg_shell.py /usr/local/bin/pkg_shell
RUN chmod +x /usr/local/bin/pkg_shell

# Create a user for SSH access with custom shell
RUN useradd -m -s /usr/local/bin/pkg_shell pkguser && \
    mkdir -p /home/pkguser/.ssh && \
    touch /home/pkguser/.ssh/authorized_keys && \
    chown -R pkguser:pkguser /home/pkguser && \
    chmod 700 /home/pkguser/.ssh && \
    chmod 600 /home/pkguser/.ssh/authorized_keys

# Configure NGINX
COPY nginx.conf /etc/nginx/nginx.conf

# Configure Dropbear SSH server
RUN mkdir -p /etc/dropbear && \
    dropbearkey -t ed25519 -f /etc/dropbear/dropbear_ed25519_host_key && \
    chown pkguser:pkguser /etc/dropbear/dropbear_ed25519_host_key && \
    bash -c 'echo -e "# /etc/shells: allow pkg_shell as the only login shell\n/usr/local/bin/pkg_shell" >/etc/shells'

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose ports
EXPOSE 8080 2222

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
