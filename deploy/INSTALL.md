# Deploying KVITKA to a server

Instructions for a clean Ubuntu 24.04. All commands run over SSH.
About an hour, half of it waiting.

How it works after installation: the server is not exposed at all, no
port except SSH is open. Traffic arrives through a Cloudflare tunnel —
the same one that may already run on your computer, just started on the
server instead. Domain and DNS settings do not change.

---

## 1. Get a server

The smallest plan is enough: 1–2 cores, 2 GB RAM, 20 GB disk.
OS — **Ubuntu 24.04**. Do not pick Windows: it is not needed here, costs
more because of the licence, and its remote desktop is brute-forced
around the clock.

**Do not install a control panel (Hestia, cPanel, ISPmanager).** Many
hosters offer one for free, and it installs its own web server that
takes the port and fights with ours. A clean server with just the OS.

Create an SSH key on your computer first — it is safer than a password:

    ssh-keygen -t ed25519

Press Enter on every question. The key lands in
`%USERPROFILE%\.ssh\id_ed25519.pub` — a text file, open it in Notepad,
the one-line content is pasted into the hoster's panel.

If the hoster does not let you upload a key at checkout and e-mails a
root password instead — no problem, add the key on first login:

    ssh root@SERVER_ADDRESS         # password from the e-mail
    mkdir -p ~/.ssh && nano ~/.ssh/authorized_keys
    # paste the content of id_ed25519.pub, save Ctrl+O, exit Ctrl+X
    chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys

Check that key login works (new window, no password), and only then
disable password login in step 2.

## 2. First login and basic hardening

    ssh root@SERVER_ADDRESS

    # update the system
    apt update && apt upgrade -y

    # a separate user for the site: nothing runs as root
    adduser --disabled-password --gecos "" kvitka
    mkdir -p /home/kvitka/.ssh
    cp ~/.ssh/authorized_keys /home/kvitka/.ssh/
    chown -R kvitka:kvitka /home/kvitka/.ssh
    chmod 700 /home/kvitka/.ssh

    # sudo for that user
    usermod -aG sudo kvitka

    # firewall: only SSH is open from outside
    apt install -y ufw
    ufw allow OpenSSH
    ufw --force enable

    # automatic security updates
    apt install -y unattended-upgrades
    dpkg-reconfigure -plow unattended-upgrades

Disable password login (only after you have confirmed that key login
works — otherwise you lock yourself out):

    nano /etc/ssh/sshd_config
    # PasswordAuthentication no
    # PermitRootLogin no
    systemctl restart ssh

## 3. Upload the project

From your computer, from the project folder:

    scp -r . kvitka@SERVER_ADDRESS:/home/kvitka/kvitka

Then on the server again, as user kvitka:

    ssh kvitka@SERVER_ADDRESS
    cd ~/kvitka

    sudo apt install -y python3-venv python3-pip sqlite3
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

## 4. Settings

    cp .env.example .env
    nano .env

Fill in `SECRET_KEY` — generate it like this:

    .venv/bin/python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

`ADMIN_ALLOWED_IPS` may stay empty for now, we return to it in step 8.

## 5. Database, translations, static files

    .venv/bin/python manage.py migrate
    .venv/bin/python manage.py compilelocales
    .venv/bin/python manage.py collectstatic --noinput
    .venv/bin/python manage.py seed_catalog     # only if the catalog is empty
    .venv/bin/python manage.py seed_pages
    .venv/bin/python manage.py seed_facets
    .venv/bin/python manage.py createsuperuser

If you bring products and photos from your computer — instead of
seed_catalog copy `db.sqlite3` and the `media` folder there:

    scp db.sqlite3 kvitka@SERVER_ADDRESS:/home/kvitka/kvitka/
    scp -r media kvitka@SERVER_ADDRESS:/home/kvitka/kvitka/

## 6. Tunnel

Copy the tunnel credentials file to the server — the one in
`%USERPROFILE%\.cloudflared\`:

    scp %USERPROFILE%\.cloudflared\TUNNEL-ID.json kvitka@SERVER_ADDRESS:/home/kvitka/.cloudflared/

Install cloudflared:

    curl -L -o /tmp/cf.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    sudo dpkg -i /tmp/cf.deb

**Important:** until the server is up, do not stop the tunnel on your
computer. One tunnel may run in two places at once — Cloudflare balances
requests between them. Once the server answers, stop the tunnel on the
computer and the site stays on the server only.

## 7. Start

    sudo cp ~/kvitka/deploy/kvitka.service /etc/systemd/system/
    sudo cp ~/kvitka/deploy/kvitka-tunnel.service /etc/systemd/system/
    sudo cp ~/kvitka/deploy/kvitka-backup.service /etc/systemd/system/
    sudo cp ~/kvitka/deploy/kvitka-backup.timer /etc/systemd/system/

    sudo systemctl daemon-reload
    sudo systemctl enable --now kvitka
    sudo systemctl enable --now kvitka-tunnel
    sudo systemctl enable --now kvitka-backup.timer

Check:

    systemctl status kvitka kvitka-tunnel
    curl -I http://127.0.0.1:8000/          # should be 200
    journalctl -u kvitka -f                  # watch it live

The site now starts by itself after a reboot and restarts if it crashes.

## 8. Admin access

Find your address: open https://ifconfig.me — a single line.
Put it into `.env`:

    ADMIN_ALLOWED_IPS=91.203.10.55

    sudo systemctl restart kvitka

Open `https://kvitka.example/admin/` — the login form should appear.
From any other address it is a 404, as if the page did not exist.

**If your address changed** (dynamic addresses from the ISP are common)
you will see a 404 instead of the form. Then:

    journalctl -u kvitka -n 50 | grep "Admin panel"

The log has a line like `Admin panel: denied address 91.203.11.7` — that
is your new address, put it into `.env` and restart the site.

To avoid editing every time, allow the ISP's whole subnet:

    ADMIN_ALLOWED_IPS=91.203.10.0/24

Slightly wider — your ISP neighbours get in too — but it still cuts off
the rest of the internet.

**Fallback that always works.** Even with an empty address list the admin
is reachable over SSH — requests from the server itself pass without
the check:

    ssh -L 8000:127.0.0.1:8000 kvitka@SERVER_ADDRESS

and, keeping that window open, visit `http://127.0.0.1:8000/admin/`.
This way you never lock yourself out, whatever happens to the address.

## 9. Backups

The timer is already on: every night at 4:00 a database snapshot and a
photo archive land in `/home/kvitka/backups`, the last 14 are kept.

Make a backup right now:

    sudo systemctl start kvitka-backup

Copy backups to your computer:

    scp -r kvitka@SERVER_ADDRESS:/home/kvitka/backups %USERPROFILE%\Desktop\

Backups sit on the same server — a disk failure takes them too.
Copy them to your computer once a month (`download-backups.bat`).

## Restoring a previous database

`adopt_content` keeps the previous database next to the new one as
`db.before-DATE.sqlite3`. To go back:

    sudo systemctl stop kvitka
    cd ~/kvitka && cp db.before-DATE.sqlite3 db.sqlite3
    sudo systemctl start kvitka

---

## Day-to-day work

Editing still happens in the project folder on your computer: run
`start.bat`, check `http://127.0.0.1:8001/`, happy — send it to the
server with `deploy-to-server.bat`.

Products, prices and orders are maintained right in the server admin —
they do not need transferring, they live in the server database.
