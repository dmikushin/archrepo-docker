# ArchRepo API Testing

This directory contains a comprehensive test suite for the ArchRepo Python API. The tests are designed to run in an isolated environment without requiring network connectivity between client and server components.

## Test Structure

The test suite includes:

- **Direct API Tests**: Tests that connect directly to the package shell without using SSH or network connections
- **Mock Shell Script**: A mock version of the pkg-shell.sh that simulates repository operations for testing
- **Dummy Package Generator**: A script that creates test .pkg.tar.zst files with signatures
- **Docker Test Environment**: A containerized test environment based on archlinux:base

## Files

- `test_direct_api.py` - Main test script that tests all API functions
- `mock_pkg_shell.sh` - Mock shell script that simulates the package repository shell
- `generate_dummy_package.sh` - Script that creates test packages for testing
- `run_tests.sh` - Script that executes all tests (locally or in Docker)
- `Dockerfile.test` - Docker configuration for the test environment
- `fixtures/` - Directory for test packages and data

## Running Tests

Running tests is simple - just execute the `run_tests.sh` script, which provides a convenient all-in-one solution:

```bash
# Navigate to the test directory
cd test/api

# Make sure scripts are executable
chmod +x *.sh

# Run the tests
./run_tests.sh
```

The script will:
1. Ask if you want to run tests in Docker (recommended) or locally
2. Set up the test environment automatically
3. Execute all the tests
4. Report the results with clear, colorized output

### Docker Mode (Recommended)

When choosing Docker mode, the script will:
- Check if Docker is installed
- Build the test Docker image automatically
- Run the container with proper environment setup
- Execute all tests in the isolated container

No additional setup is required - everything is handled by the script.

### Local Mode

If you prefer to run tests directly on your system:
- Requires Arch Linux with all dependencies installed
- The script will check for required tools
- Tests will run directly on your local system

## Test Coverage

The test suite covers all major API functions:

1. **Publishing Packages**
   - With signatures
   - Without signatures

2. **Listing Packages**
   - Verifying package metadata structure

3. **Removing Packages**
   - Testing package removal
   - Verifying removal was successful

4. **Repository Cleaning**
   - Adding multiple package versions
   - Verifying only the latest version is kept

5. **Status Information**
   - Getting repository statistics
   - Verifying status information format

## How It Works

The tests bypass the network/SSH layer of the API by:

1. Mocking the SSH connection process
2. Connecting the API directly to the mock shell script
3. Using direct file operations instead of network transfers

This approach allows for comprehensive testing with these advantages:
- No need for actual SSH connections
- Faster test execution
- Isolated test environment
- Reproducible test results

## Extending the Tests

To add new tests:

1. Add test methods to the `TestDirectArchRepoAPI` class in `test_direct_api.py`
2. Follow the naming convention `test_*` for new test methods
3. If needed, add supporting functions to `mock_pkg_shell.sh`

## Requirements

- For Docker mode: Docker installed and running
- For local mode:
  - Python 3.6+
  - Arch Linux
  - Base development tools (`pacman -S base-devel`)
  - Python testing packages (`pip install pytest`)
  - Pacman contrib tools (`pacman -S pacman-contrib`)
