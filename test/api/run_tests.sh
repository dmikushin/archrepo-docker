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

# Check if running in Docker already
if [ "$IN_DOCKER" = "1" ]; then
    echo -e "${YELLOW}Running tests inside Docker container...${NC}"

    # Setup test environment
    echo -e "${YELLOW}Setting up test environment...${NC}"
    mkdir -p /tmp/test_repo/x86_64
    mkdir -p /tmp/uploads

    # Initialize repo database if needed
    if [ ! -f /tmp/test_repo/x86_64/repo.db.tar.gz ]; then
        echo -e "${YELLOW}Initializing repository database...${NC}"
        pushd /tmp/test_repo/x86_64
        repo-add repo.db.tar.gz
        popd
    fi

    # Generate dummy package if needed
    if [ ! -f ./fixtures/test-package-1.0.0-1-x86_64.pkg.tar.zst ]; then
        echo -e "${YELLOW}Generating dummy package...${NC}"
        ./generate_dummy_package.sh
    fi

    # Make sure Python modules are accessible
    echo -e "${YELLOW}Setting up Python environment...${NC}"
    # Copy main module to Python path if not already installed
    if [ ! -f $(python -c "import sys; print(next(p for p in sys.path if p.endswith('site-packages')))")/pkg_shell.py ]; then
        cp pkg_shell.py $(python -c "import sys; print(next(p for p in sys.path if p.endswith('site-packages')))")
    fi

    # Make the mock shell executable
    chmod +x mock_pkg_shell.py

    # Run the tests
    echo -e "${YELLOW}Running API tests...${NC}"
    cd /app
    python -m unittest discover -s test/api

    # Check result
    if [ $? -eq 0 ]; then
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

    if [ "$choice" = "1" ]; then
        echo -e "${YELLOW}Running tests in Docker container...${NC}"

        # Get repository root directory (assuming run from test/api)
        REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)

        # Check if Docker is available
        if ! command -v docker &> /dev/null; then
            echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
            exit 1
        fi

        echo -e "${YELLOW}Building Docker image...${NC}"
        docker build -f "${REPO_ROOT}/test/api/Dockerfile.test" -t archrepo-test "${REPO_ROOT}"

        echo -e "${YELLOW}Running tests in container...${NC}"
        docker run --rm archrepo-test

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

        # Initialize repo database if needed
        if [ ! -f /tmp/test_repo/x86_64/repo.db.tar.gz ]; then
            echo -e "${YELLOW}Initializing repository database...${NC}"
            cd /tmp/test_repo/x86_64
            repo-add repo.db.tar.gz
        fi

        # Generate dummy package if needed
        if [ ! -f ./fixtures/test-package-1.0.0-1-x86_64.pkg.tar.zst ]; then
            echo -e "${YELLOW}Generating dummy package...${NC}"
            ./generate_dummy_package.sh
        fi

        # Make sure Python modules are accessible
        echo -e "${YELLOW}Setting up Python environment...${NC}"
        # Copy main module to Python path if not already installed
        PYTHON_SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
        if [ ! -f "$PYTHON_SITE_PACKAGES/pkg_shell.py" ]; then
            sudo cp pkg_shell.py "$PYTHON_SITE_PACKAGES/"
        fi

        # Make the mock shell executable
        chmod +x mock_pkg_shell.py

        # Run the tests
        echo -e "${YELLOW}Running API tests...${NC}"
        python -m unittest discover

        # Check result
        if [ $? -eq 0 ]; then
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
