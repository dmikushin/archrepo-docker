# ArchRepo API Testing

This directory contains a comprehensive test suite for the ArchRepo Python API. The tests are designed to run in an isolated environment without requiring network connectivity between client and server components.

## Test Structure

The test suite includes:

- **Direct API Tests**: Tests that connect directly to the package shell without using SSH or network connections
- **Dummy Package Generator**: A script that creates test .pkg.tar.zst files with signatures
- **Docker Test Environment**: A containerized test environment based on archlinux:base

## Files

- `test_direct_api.py` - Main test script that tests all API functions
- `generate_dummy_package.sh` - Script that creates test packages for testing
- `run_tests.sh` - Script that executes all tests (locally or in Docker)
- `Dockerfile` - Docker configuration for the test environment

## Running Tests

Running tests is simple - just execute the `run_tests.sh` script, which provides a convenient all-in-one solution:

```bash
# Navigate to the test directory
cd test/api

# Run the tests
./run_tests.sh
```

The script will:
- Check if Docker is installed
- Build the test Docker image automatically
- Run the container with proper environment setup
- Execute all tests in the isolated container
- Report the testing result

No additional setup is required - everything is handled by the script.

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

