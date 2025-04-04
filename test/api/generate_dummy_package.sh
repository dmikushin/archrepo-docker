#!/bin/bash
# generate_dummy_package.sh - Creates a dummy Arch Linux package for testing

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

# Create package structure
echo "Creating dummy package structure..."
mkdir -p "pkg/usr/bin"
mkdir -p "pkg/usr/share/doc/${PKG_NAME}"

# Add a dummy executable
cat > "pkg/usr/bin/${PKG_NAME}" << EOF
#!/bin/sh
echo "This is a dummy test package for archrepo testing"
exit 0
EOF
chmod +x "pkg/usr/bin/${PKG_NAME}"

# Add documentation
cat > "pkg/usr/share/doc/${PKG_NAME}/README" << EOF
# ${PKG_NAME}

This is a dummy package created for testing the archrepo API.
It doesn't actually do anything useful.

Version: ${PKG_VER}
Release: ${PKG_REL}
EOF

# Create .PKGINFO file
cat > "pkg/.PKGINFO" << EOF
pkgname = ${PKG_NAME}
pkgver = ${PKG_VER}-${PKG_REL}
pkgdesc = A dummy package for archrepo testing
url = https://github.com/dmikushin/archrepo-docker
builddate = $(date +%s)
packager = Test Script <test@example.com>
size = 0
arch = ${ARCH}
license = MIT
EOF

# Create a compressed package using tar and zstd
echo "Creating package archive..."
cd pkg
tar -cf "../${PKG_NAME}.tar" ./*
cd ..
zstd -19 "${PKG_NAME}.tar" -o "${PKG_FILENAME}"
rm "${PKG_NAME}.tar"

# Create a dummy signature file
echo "Creating dummy signature file..."
echo "THIS IS A DUMMY SIGNATURE FOR TESTING PURPOSES ONLY" > "${PKG_FILENAME}.sig"

echo "Package created: ${PKG_FILENAME}"
echo "Signature created: ${PKG_FILENAME}.sig"

# Clean up temporary files
rm -rf pkg

# Show package info
echo "Package details:"
ls -lh "${PKG_FILENAME}"*
echo "Done!"
