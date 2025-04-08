#!/bin/bash
# run_tests.sh - Run all ArchRepo API tests in a dedicated Docker container
set -e

# Get repository root directory (assuming run from test/api)
REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "Error: Docker is not installed or not in PATH"
    exit 1
fi

# First, make sure the fresh base image is built
pushd ${REPO_ROOT}
docker build -t archrepo .
popd

echo -e "Building Docker image..."
docker build -f "${REPO_ROOT}/test/api/Dockerfile" -t archrepo-test "${REPO_ROOT}"

echo -e "Running tests in container..."

# Mount a volume for logs
mkdir -p ${REPO_ROOT}/test/api/tmp
docker run --rm -v ./tmp:/tmp/ archrepo-test

# Display logs if they exist and are not empty
if [ -s ./tmp/logs/pkg_shell_test_errors.log ] || [ -s ./tmp/logs/pkg_shell_direct_test_errors.log ]; then
    echo -e "= Error logs from tests: ="
    echo -e "= Main test error log: ="
    cat ./tmp/logs/pkg_shell_test_errors.log
    echo -e "= Direct test error log: ="
    cat ./tmp/logs/pkg_shell_direct_test_errors.log
fi

echo -e "Docker test run complete!"
