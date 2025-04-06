FROM archrepo

# Install Python pip and Git for package installation
RUN pacman -Sy --noconfirm python-pipx git

# Install quasipkg
RUN pipx install --global git+https://github.com/dmikushin/quasipkg.git

# Create test-specific directories and files
RUN mkdir -p /tmp/test_repo/x86_64 \
    && mkdir -p /tmp/uploads \
    && mkdir -p /tmp/logs \
    && touch /tmp/pkg_shell_test_errors.log \
    && touch /tmp/pkg_shell_direct_test_errors.log \
    && chmod 666 /tmp/pkg_shell_test_errors.log \
    && chmod 666 /tmp/pkg_shell_direct_test_errors.log

# Set environment variables for testing
ENV TEST_MODE=1
ENV REPO_DIR=/tmp/test_repo/x86_64
ENV DB_NAME=repo.db.tar.zst
ENV UPLOAD_DIR=/tmp/uploads
ENV HISTORY_FILE=/tmp/pkg_shell_test_history
ENV ERROR_LOG_FILE=/tmp/pkg_shell_test_errors.log

# Create volume for logs
VOLUME ["/tmp/logs"]

WORKDIR /app

COPY . .

# Set working directory for tests
WORKDIR /app/test/api

# Set the test command to run
CMD ["/entrypoint.sh"]
