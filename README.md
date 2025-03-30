# archrepo-docker: ArchLinux Package Repository Container

Set up, use, and manage your custom ArchLinux package repository using a specialized SSH interface.

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


## Package Management via SSH Interface

Instead of a general-purpose shell, this container provides a specialized repository management interface when you connect via SSH.

### SSH Access

The first time you run the container, it will generate an SSH key pair in the `./ssh-keys` directory. You should use this key to authenticate with the server.

1. Add the generated SSH key to your SSH configuration:

   ```bash
   ssh-add ./ssh-keys/id_ed25519
   ```

2. Connect to the repository management shell:

   ```bash
   ssh -i ./ssh-keys/id_ed25519 -p 2222 pkguser@your-server-ip
   ```

### Available Commands

The SSH interface provides the following commands:

- `add <package-file.pkg.tar.zst>` - Add a package to the repository
- `remove <package-name>` - Remove a package from the repository
- `list` - List all packages in the repository
- `clean` - Clean up old package versions
- `receive <filename>` - Receive a package file through the SSH connection
- `send <filename>` - Send a file from the repository to the client
- `status` - Show repository statistics
- `help` - Show help menu
- `exit` - Log out

### Uploading Packages

There are two ways to upload packages:

#### Method 1: Using the integrated file transfer

1. Build your package using makepkg as usual:
   ```bash
   git clone https://aur.archlinux.org/package-name.git
   cd package-name
   makepkg -s
   ```

2. SSH into the repository:
   ```bash
   ssh -i ./ssh-keys/id_ed25519 -p 2222 pkguser@your-server-ip
   ```

3. Use the `receive` command to upload your package:
   ```
   pkgrepo> receive your-package-1.0-1-x86_64.pkg.tar.zst
   ```

4. When prompted, paste the base64-encoded content of your package file. You can create this with:
   ```bash
   base64 your-package-1.0-1-x86_64.pkg.tar.zst
   ```

5. After pasting the content, type `EOF` on a new line to complete the transfer.

6. Add the package to the repository:
   ```
   pkgrepo> add /home/pkguser/uploads/your-package-1.0-1-x86_64.pkg.tar.zst
   pkgrepo> exit
   ```

#### Method 2: Using SCP (separate from the shell)

1. Upload your package using `scp`:
   ```bash
   scp -P 2222 your-package-1.0-1-x86_64.pkg.tar.zst pkguser@your-server-ip:~/uploads/
   ```

2. SSH into the repository and add the package to the database:
   ```bash
   ssh -i ./ssh-keys/id_ed25519 -p 2222 pkguser@your-server-ip
   pkgrepo> add /home/pkguser/uploads/your-package-1.0-1-x86_64.pkg.tar.zst
   pkgrepo> exit
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
