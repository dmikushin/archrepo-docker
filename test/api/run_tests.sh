#!/bin/bash
# run_tests.sh - Run all ArchRepo API tests (locally or in Docker)

set -e

# Colors for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Display banner
echo -e "${GREEN}=======================================================${NC}"
echo -e "${GREEN}         ArchRepo API Test Suite Runner                ${NC}"
echo -e "${GREEN}=======================================================${NC}"

# Create error log directories
setup_error_logs() {
    echo -e "${YELLOW}Setting up error logs...${NC}"
    mkdir -p /tmp/logs
    # Create or clear error log files
    > /tmp/pkg_shell_test_errors.log
    > /tmp/pkg_shell_direct_test_errors.log
    chmod 666 /tmp/pkg_shell_test_errors.log
    chmod 666 /tmp/pkg_shell_direct_test_errors.log
    echo "Error logs will be stored in /tmp/logs/"
}

# Check if running in Docker already
if [ "$IN_DOCKER" = "1" ]; then
    echo -e "${YELLOW}Running tests inside Docker container...${NC}"

    # Setup test environment
    echo -e "${YELLOW}Setting up test environment...${NC}"
    mkdir -p /tmp/test_repo/x86_64
    mkdir -p /tmp/uploads

    # Setup error logs
    setup_error_logs

    # Generate dummy package if needed
    if [ ! -f ./fixtures/test-package-1.0.0-1-x86_64.pkg.tar.zst ]; then
        echo -e "${YELLOW}Generating dummy package...${NC}"
        ./generate_dummy_package.sh
    fi

    # Run the tests
    echo -e "${YELLOW}Running API tests...${NC}"
    cd /app

    # Save test results
    TEST_RESULT=0
    python -m unittest discover -s test/api || TEST_RESULT=$?

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

else
    # Not in Docker, ask if user wants to run locally or in Docker
    echo -e "${YELLOW}Choose test environment:${NC}"
    echo "1) Run in Docker (recommended, requires Docker)"
    echo "2) Run locally (requires Arch Linux with dependencies)"
    read -p "Enter choice [1]: " choice

    # Default to Docker
    choice=${choice:-1}

    # Get repository root directory (assuming run from test/api)
    REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)

    if [ "$choice" = "1" ]; then
        echo -e "${YELLOW}Running tests in Docker container...${NC}"

        # Check if Docker is available
        if ! command -v docker &> /dev/null; then
            echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
            exit 1
        fi

        echo -e "${YELLOW}Building Docker image...${NC}"
        docker build -f "${REPO_ROOT}/test/api/Dockerfile.test" -t archrepo-test "${REPO_ROOT}"

        echo -e "${YELLOW}Running tests in container...${NC}"
        # Mount a volume for logs
        mkdir -p /tmp/logs
        docker run --rm -v /tmp/logs:/tmp/logs archrepo-test

        # Display logs if they exist and are not empty
        if [ -s /tmp/logs/pkg_shell_test_errors.log ] || [ -s /tmp/logs/pkg_shell_direct_test_errors.log ]; then
            echo -e "${YELLOW}Error logs from tests:${NC}"
            echo -e "${YELLOW}Main test error log:${NC}"
            cat /tmp/logs/pkg_shell_test_errors.log
            echo -e "${YELLOW}Direct test error log:${NC}"
            cat /tmp/logs/pkg_shell_direct_test_errors.log
        fi

        echo -e "${GREEN}Docker test run complete!${NC}"

    else
        echo -e "${YELLOW}Running tests locally...${NC}"

        # Check if required tools are available
        if ! command -v repo-add &> /dev/null; then
            echo -e "${RED}Error: pacman-contrib (repo-add tool) is not installed${NC}"
            echo "Please install with: sudo pacman -S pacman-contrib"
            exit 1
        fi

        if ! command -v python &> /dev/null; then
            echo -e "${RED}Error: Python is not installed${NC}"
            echo "Please install with: sudo pacman -S python"
            exit 1
        fi

        # Setup test environment
        echo -e "${YELLOW}Setting up local test environment...${NC}"
        mkdir -p /tmp/test_repo/x86_64
        mkdir -p /tmp/uploads

        # Setup error logs
        setup_error_logs

        # Generate dummy package if needed
        if [ ! -f ./fixtures/test-package-1.0.0-1-x86_64.pkg.tar.zst ]; then
            echo -e "${YELLOW}Generating dummy package...${NC}"
            ./generate_dummy_package.sh
        fi

        # Make the pkg_shell executable
        chmod +x "${REPO_ROOT}/pkg_shell.py"

        # Run the tests
        echo -e "${YELLOW}Running API tests...${NC}"
        TEST_RESULT=0
        python -m unittest discover || TEST_RESULT=$?

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
    fi
fi

echo -e "${GREEN}=======================================================${NC}"
echo -e "${GREEN}         Test run complete                             ${NC}"
echo -e "${GREEN}=======================================================${NC}"
