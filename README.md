# archrepo-docker: ArchLinux Package Repository Container

Setup your custom ArchLinux package repository and manage it using a Python API.


## Setting Up the Server Container

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

```
git clone https://github.com/dmikushin/archrepo.git
cd archrepo
pip install .
```

### Usage

After installation, the `archrepo` command will be available in your `PATH`:

```bash
# Show help
archrepo --help

# Publish a package in the repository
archrepo -H ssh_server publish mypackage-1.0-1-x86_64.pkg.tar.zst

# List packages in the repository
archrepo -H ssh_server list

# Remove a package from the repository
archrepo -H ssh_server remove mypackage

# Check repository status
archrepo -H ssh_server status
```

The `-H` option must be followed by a valid `Host` name entry of `.ssh/config`, for example:

```
Host ssh_server
    Hostname archrepo.user.me
    User pkgconfig
    Port 2222
    IdentityFile /path/to/ssh-keys/id_ed25519
```

The `IdentityFile` referred to by SSH config must be a copy of `./ssh-keys/id_ed25519` file created by the server upon the first Docker container execution. This key is for maintainer's use only, and must be kept secured.

### Building and Publishing Packages

1. Build your package using makepkg as usual:

   ```bash
   git clone https://aur.archlinux.org/package-name.git
   cd package-name
   makepkg -s
   ```

2. Publish the package to your repository:

   ```bash
   archrepo -H ssh_server publish ./your-package-1.0-1-x86_64.pkg.tar.zst
   ```


## Security Considerations

For production use, consider these additional security enhancements:

1. **Enable HTTPS** for package downloads by configuring Nginx with SSL.
2. **Set up package signing** for better security.


## Maintenance

- **Logs**: SSH command history is stored in `/home/pkguser/.pkg_shell_history`
- **Backup**: The `repo-data` volume contains all your packages.
- **Cleanup**: Use the `clean` command to remove old package versions.
- **Monitoring**: Use the `status` command to check disk space usage and repository statistics.
