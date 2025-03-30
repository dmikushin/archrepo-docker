# archrepo-docker: ArchLinux Package Repository Container

Set up, use, and manage your custom ArchLinux package repository.

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


## Uploading Packages

### Building a Package

1. Create a basic package:
   ```bash
   git clone https://aur.archlinux.org/package-name.git
   cd package-name
   makepkg -s
   ```

2. This will create a `.pkg.tar.zst` file.

### Uploading via SSH

The first time you run the container, it will generate an SSH key pair in the `./ssh-keys` directory. You should use this key to authenticate with the server.

1. Add the generated SSH key to your SSH configuration:

   ```bash
   ssh-add ./ssh-keys/id_ed25519
   ```

2. Upload your package using `scp`:

   ```bash
   scp -P 2222 your-package-1.0-1-x86_64.pkg.tar.zst pkguser@your-server-ip:/srv/repo/x86_64/
   ```

3. If you're using this system on a different machine, copy the public key to your local machine:

   ```bash
   cat ./ssh-keys/id_ed25519.pub >> ~/.ssh/authorized_keys
   ```

### Updating the Repository Database

After uploading, SSH into the repository to update the database:

```bash
ssh -i ./ssh-keys/id_ed25519 -p 2222 pkguser@your-server-ip
cd /srv/repo/x86_64
repo-add repo.db.tar.gz *.pkg.tar.zst
exit
```


## Security Considerations

For production use, consider these additional security enhancements:

1. **Keep your SSH keys secure** and consider setting a passphrase when generating them.
2. **Restrict the SSH server** to only allow specific IP addresses.
3. **Enable HTTPS** for package downloads by configuring Nginx with SSL.
4. **Set up package signing** for better security.


## Maintenance

- **Backup**: The `repo-data` volume contains all your packages.
- **Cleanup**: Periodically remove old package versions.
- **Monitoring**: Check disk space usage regularly.
