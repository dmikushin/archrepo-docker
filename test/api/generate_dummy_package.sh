#!/bin/bash
# generate_dummy_package.sh - Creates a dummy Arch Linux package for testing using quasipkg

set -e

# Directory setup
TEST_DIR="$(pwd)"
mkdir -p "${TEST_DIR}/fixtures"
cd "${TEST_DIR}/fixtures"

PKG_NAME="test-package"
PKG_VER="1.0.0"
PKG_REL="1"
ARCH="x86_64"
PKG_FILENAME="${PKG_NAME}-${PKG_VER}-${PKG_REL}-${ARCH}.pkg.tar.zst"

echo "Creating dummy package using quasipkg..."

# Create package with quasipkg
quasipkg --name "${PKG_NAME}" \
         --pkgversion "${PKG_VER}" \
         --release "${PKG_REL}" \
         --description "A dummy package for archrepo testing" \
         --provides "${PKG_NAME}" \
         --arch "${ARCH}" \
         --license "MIT" \
         --url "https://github.com/dmikushin/archrepo-docker" \
         --output-dir "test-pkg-build"

# Build the package using quasipkg (the package should be built in the output-dir)
cd "test-pkg-build"
makepkg -f

# Copy the built package to fixtures directory
cp *.pkg.tar.zst ../ || echo "Error: Failed to find built package"
cd ..

# Create a dummy signature file (since quasipkg doesn't handle signatures)
echo "Creating dummy signature file..."
echo "THIS IS A DUMMY SIGNATURE FOR TESTING PURPOSES ONLY" > "${PKG_FILENAME}.sig"

echo "Package created: ${PKG_FILENAME}"
echo "Signature created: ${PKG_FILENAME}.sig"

# Clean up temporary build files
rm -rf "test-pkg-build"

# Show package info
echo "Package details:"
ls -lh "${PKG_FILENAME}"*
echo "Done!"
