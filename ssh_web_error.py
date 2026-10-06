#!/usr/bin/env python3
"""recup les try d'auth qui on fail, dans les logs
Nginx (auth basic) et les enregistre dans la base psmm (service 'web')."""


import re
import sys
from datetime import datetime
from config import SERVERS
from ssh_login_sudo import ssh_sudo
from ssh_mysql_error import save_errors

LOG_FILE = "/var/log/nginx/error.log"

# 2 formats de lignes d'échec :
# 2026/10/04 16:10:49 [error] 2432#2432: *1 user "msl" was not found in "/etc/nginx/.htpasswd", client: 192.168.25.1, ...
# 2026/10/04 16:12:03 [error] 2432#2432: *3 user "slm": password mismatch, client: 192.168.25.1, ...
PATTERN = re.compile(
    r'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[error\] \d+#\d+: \*\d+ '
    r'user "([^"]*)"(?: was not found in "[^"]*"|: password mismatch), '
    r'client: ([0-9a-fA-F:.]+)'
)


def parse_log(text):
    """return la liste des tentatives : (username, ip, datetime, ligne brute)."""
    errors = []
    for line in text.splitlines():
        m = PATTERN.search(line)
        if m:
            when_str, user, ip = m.groups()
            when = datetime.strptime(when_str, "%Y/%m/%d %H:%M:%S")
            errors.append((user, ip, when, line.strip()))
    return errors


def main():
    host = SERVERS["web"]
    print(f"lecture de {LOG_FILE} sur {host}...")
    # zcat -f lit aussi les anciens logs (rotation .1 et .gz)
    code, out, err = ssh_sudo(host, f"zcat -f {LOG_FILE}*")
    if code != 0:
        print(f"[ERREUR] impossible de lire le log : {err.strip()}")
        sys.exit(1)

    errors = parse_log(out)
    print(f"{len(errors)} tentative(s) refusée(s) trouvée(s) dans le log :\n")
    print(f"{'Date/heure':<20} {'Compte':<20} {'IP'}")
    print("-" * 60)
    for user, ip, when, _ in errors:
        print(f"{when:%Y-%m-%d %H:%M:%S}  {user:<20} {ip}")

    new = save_errors("web", errors)
    print(f"\n[OK] {new} nouvelle(s) tentative(s) enregistrée(s) en base "
          f"({len(errors) - new} déjà présente(s)).")


if __name__ == "__main__":
    main()
