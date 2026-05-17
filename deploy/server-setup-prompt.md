# QuickReddit — server setup prompt for Claude Code

You are setting up QuickReddit on this Linux server. QuickReddit is a personal Reddit digest tool: a Python script fetches top posts + comments from a configured set of subreddits, optionally summarises them via an LLM (OpenRouter API), and writes the result to `reddit_data.json`. A static `reddit_report.html` loads that JSON in the browser via a `fetch()` call. No backend beyond a web server is needed.

The server already has: Apache2, Let's Encrypt / certbot, Python 3, git.

## What you need to do

Work through every step below in order. Run commands directly. If a step requires input from me (domain name, password, API key), ask for it before proceeding.

---

### Step 0 — gather variables

Ask me for these before doing anything else:
- **DOMAIN** — the subdomain to serve QuickReddit on (e.g. `reddit.example.com`)
- **DEPLOY_USER** — the Linux user that GitHub Actions will SSH in as (default: current user)
- **HTPASSWD_USER** — username for basic auth (e.g. `coen`)
- **OPENROUTER_API_KEY** — the API key for LLM summaries (starts with `sk-`)

---

### Step 1 — clone the repo

```bash
sudo git clone https://github.com/shifthappens/QuickReddit /var/www/quickreddit
sudo chown -R $DEPLOY_USER:www-data /var/www/quickreddit
sudo chmod -R 755 /var/www/quickreddit
```

---

### Step 2 — deploy script

Create `/var/www/quickreddit/deploy.sh`:

```bash
#!/bin/bash
set -e
cd /var/www/quickreddit
git pull origin main
```

Make it executable:
```bash
chmod +x /var/www/quickreddit/deploy.sh
```

---

### Step 3 — API key

Store the key so only root and the cron user can read it:

```bash
echo "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" | sudo tee /etc/quickreddit.env
sudo chmod 600 /etc/quickreddit.env
```

---

### Step 4 — Apache VirtualHost

Create `/etc/apache2/sites-available/quickreddit.conf`:

```apache
<VirtualHost *:80>
    ServerName $DOMAIN
    DocumentRoot /var/www/quickreddit

    <Directory /var/www/quickreddit>
        Options None
        AllowOverride None
        AuthType Basic
        AuthName "QuickReddit"
        AuthUserFile /etc/apache2/.htpasswd-quickreddit
        Require valid-user
    </Directory>
</VirtualHost>
```

Enable the site and required modules:
```bash
sudo a2enmod auth_basic authn_file
sudo a2ensite quickreddit.conf
sudo systemctl reload apache2
```

---

### Step 5 — basic auth password

```bash
sudo htpasswd -c /etc/apache2/.htpasswd-quickreddit $HTPASSWD_USER
```
(You will be prompted for a password.)

---

### Step 6 — Let's Encrypt

```bash
sudo certbot --apache -d $DOMAIN
```

Certbot will update the VirtualHost config automatically. Verify the site loads over HTTPS before continuing.

---

### Step 7 — cron job

Add a cron entry for the deploy user to run the fetch script every day at 06:00:

```bash
(crontab -l 2>/dev/null; echo "0 6 * * * cd /var/www/quickreddit && env \$(cat /etc/quickreddit.env) python3 reddit_viewer.py >> /var/log/quickreddit.log 2>&1") | crontab -
```

Create the log file:
```bash
sudo touch /var/log/quickreddit.log
sudo chown $DEPLOY_USER /var/log/quickreddit.log
```

---

### Step 8 — bootstrap

Run the script once to generate `reddit_data.json`:

```bash
cd /var/www/quickreddit && env $(cat /etc/quickreddit.env) python3 reddit_viewer.py
```

Confirm `reddit_data.json` exists, then open `https://$DOMAIN/reddit_report.html` in a browser to verify the report loads.

---

### Step 9 — SSH key for GitHub Actions

Generate a dedicated deploy key (no passphrase):

```bash
ssh-keygen -t ed25519 -C "github-actions-quickreddit" -f ~/.ssh/quickreddit_deploy -N ""
cat ~/.ssh/quickreddit_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/quickreddit_deploy      # copy this — it's the GitHub Actions secret
```

Then tell me the public key and the private key output so I can give you the next instructions.

---

### Step 10 — GitHub Actions secrets

In the GitHub repo (`shifthappens/QuickReddit`), go to **Settings → Secrets and variables → Actions** and add:

| Secret name   | Value                                      |
|---------------|--------------------------------------------|
| `DEPLOY_HOST` | server IP or hostname                      |
| `DEPLOY_USER` | the Linux user from Step 0                 |
| `DEPLOY_KEY`  | private key from `~/.ssh/quickreddit_deploy` (full contents including header/footer) |

After adding these secrets, push any commit to `main` and confirm the Actions workflow runs successfully and `deploy.sh` is called on the server.

---

### Verification checklist

- [ ] `https://$DOMAIN/reddit_report.html` loads and prompts for basic auth
- [ ] Report shows posts after logging in
- [ ] `crontab -l` shows the 06:00 job
- [ ] A push to `main` triggers the GitHub Actions deploy and runs `deploy.sh` on the server
- [ ] `/var/log/quickreddit.log` is writable and captures cron output
