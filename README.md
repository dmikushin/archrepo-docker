# archrepo-docker: ArchLinux Package Repository Container

Setup your custom ArchLinux package repository and manage it using a Python API.


## Setting Up the Repository

1. Clone this repository into a folder intended to be a package repository

2. Build and start the container:

   ```bash
   docker-compose up -d
   ```

3. The repository should now be running at http://localhost:8080 and SSH accessible on port 2222.


## Client Setup: Configuring Pacman

Add your repository to `/etc/pacman.conf` on your Arch Linux clients:

```ini
[custom]
SigLevel = Optional TrustAll
Server = http://your-server-ip:8080/x86_64
```

After adding this, update the package database:

```bash
sudo pacman -Sy
```


## Package Management via Python API

A Python API is used to provide a secure server connection to manage your package repository.

### Installation

```bash
# Clone the repository 
git clone https://github.com/yourusername/archrepo-api.git
cd archrepo-api

# Install dependencies (minimal dependencies required)
pip install -r requirements.txt
```

### SSH Key Setup

The first time you run the container, it will generate an SSH key pair in the `./ssh-keys` directory. You should use this key for authentication.

1. Add the generated SSH key to your SSH configuration:

   ```bash
   ssh-add ./ssh-keys/id_ed25519
   ```

2. Make sure the key has the correct permissions:

   ```bash
   chmod 600 ./ssh-keys/id_ed25519
   ```

### Command-line Usage

The module can be used as a command-line tool:

```bash
# Upload a package
python3 archrepo.py upload mypackage-1.0-1-x86_64.pkg.tar.zst --add

# Add a previously uploaded package to the repository
python3 archrepo.py add /home/pkguser/uploads/mypackage-1.0-1-x86_64.pkg.tar.zst

# Remove a package from the repository
python3 archrepo.py remove mypackage

# List all packages in the repository
python3 archrepo.py list

# Clean up old package versions
python3 archrepo.py clean

# Check repository status
python3 archrepo.py status

# Download a package from the repository
python3 archrepo.py download mypackage-1.0-1-x86_64.pkg.tar.zst -o ./downloaded.pkg.tar.zst
```

### Python API Usage

You can use the API programmatically in your own Python code:

```python
from archrepo import ArchRepoClient

# Initialize the client
client = ArchRepoClient(
    host="your-server-ip",
    port="2222",
    user="pkguser",
    key_path="./ssh-keys/id_ed25519"
)

# Upload a package and add it to the repository
success, message = client.upload_package("mypackage-1.0-1-x86_64.pkg.tar.zst", add_to_repo=True)
print(message)  # "Package uploaded and added to repository successfully."

# List all packages
success, packages = client.list_packages()
if success:
    for pkg in packages:
        print(f"{pkg['name']} {pkg['version']} - {pkg['description']}")

# Get repository status
success, status = client.get_status()
if success:
    print(f"Total packages: {status.get('Total packages', 'Unknown')}")
    print(f"Repository size: {status.get('Repository size', 'Unknown')}")
```

### Building and Uploading Packages

1. Build your package using makepkg as usual:
   ```bash
   git clone https://aur.archlinux.org/package-name.git
   cd package-name
   makepkg -s
   ```

2. Upload and add the package to your repository:
   ```bash
   python3 archrepo.py upload ./your-package-1.0-1-x86_64.pkg.tar.zst --add
   ```

### Available API Methods

The Python API provides the following functionality:

- **upload_package(package_path, add_to_repo=False)** - Upload a package to the repository
- **add_package(package_name)** - Add a previously uploaded package to the repository
- **remove_package(package_name)** - Remove a package from the repository
- **list_packages()** - List all packages in the repository
- **clean_repository()** - Clean up old package versions
- **get_status()** - Show repository statistics
- **download_package(package_name, output_path=None)** - Download a package from the repository

### Environment Variables

You can configure the connection details using environment variables:

- `SSH_HOST`: SSH host (default: localhost)
- `SSH_PORT`: SSH port (default: 2222)
- `SSH_USER`: SSH username (default: pkguser)
- `SSH_KEY`: Path to SSH key file (default: ./ssh-keys/id_ed25519)

Example:
```bash
export SSH_HOST=my-repo-server.example.com
export SSH_KEY=~/.ssh/repo_key
python3 archrepo.py list
```


## Security Considerations

For production use, consider these additional security enhancements:

1. **Keep your SSH keys secure** and consider setting a passphrase when generating them.
2. **Restrict the SSH server** to only allow specific IP addresses.
3. **Enable HTTPS** for package downloads by configuring Nginx with SSL.
4. **Set up package signing** for better security.


## Maintenance

- **Logs**: SSH command history is stored in `/home/pkguser/.pkg_shell_history`
- **Backup**: The `repo-data` volume contains all your packages.
- **Cleanup**: Use the `clean` command to remove old package versions.
- **Monitoring**: Use the `status` command to check disk space usage and repository statistics.
