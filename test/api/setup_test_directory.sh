#!/bin/bash
# setup_test_directory.sh - Creates the test directory structure and installs test files

set -e

# Root directory is the current project directory
ROOT_DIR=$(pwd)
TEST_DIR="${ROOT_DIR}/test/api"

# Create directory structure
echo "Creating test directory structure..."
mkdir -p "${TEST_DIR}/fixtures"

# Copy test files to the appropriate locations
echo "Installing test files..."

# Copy test scripts
cat > "${TEST_DIR}/mock_pkg_shell.py" << 'EOF'
#!/bin/bash
# The content of mock_pkg_shell.py will be inserted here
EOF

cat > "${TEST_DIR}/generate_dummy_package.sh" << 'EOF'
#!/bin/bash
# The content of generate_dummy_package.sh will be inserted here
EOF

cat > "${TEST_DIR}/test_direct_api.py" << 'EOF'
#!/usr/bin/env python3
# The content of test_direct_api.py will be inserted here
EOF

cat > "${TEST_DIR}/run_tests.sh" << 'EOF'
#!/bin/bash
# The content of run_tests.sh will be inserted here
EOF

cat > "${TEST_DIR}/Dockerfile.test" << 'EOF'
# The content of Dockerfile.test will be inserted here
EOF

# Make scripts executable
chmod +x "${TEST_DIR}/mock_pkg_shell.py"
chmod +x "${TEST_DIR}/generate_dummy_package.sh"
chmod +x "${TEST_DIR}/run_tests.sh"
chmod +x "${TEST_DIR}/test_direct_api.py"

echo "Test directory setup complete!"
echo "To run tests, use: cd test/api && ./run_tests.sh"
