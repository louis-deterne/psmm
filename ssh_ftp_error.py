#!/usr/bin/env python3
"""recup les tentatives de connexion FTP qui on fail, dans les logs
ProFTPD et les save dans la base psmm (table access_errors, service 'ftp'). """


import re
import sys
from datetime import datetime
from config import SERVERS
from ssh_login_sudo import ssh_sudo
from ssh_mysql_error import save_errors

LOG_FILE = "/var/log/proftpd/proftpd.log"

# 2 formats de lignes d'echec :
# ... slm-ftp (192.168.25.1[192.168.25.1]): USER test: no such user found from ...
# ... slm-ftp (192.168.25.1[192.168.25.1]): USER ftpuser (Login failed): Incorrect password
PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+\S+\s+proftpd\[\d+\]\s+\S+\s+"
    r"\([^\[]*\[([^\]]+)\]\):\s+USER\s+(\S+?)"
    r"(:\s+no such user found|\s+\(Login failed\))"
)


def parse_log(text):
    """return la liste des tentatives : (username, ip, datetime, ligne brute)."""
    errors = []
    for line in text.splitlines():
        m = PATTERN.search(line)
        if m:
            when_str, ip, user, _ = m.groups()
            ip = ip.replace("::ffff:", "")          # adresse IPv4 mappée en IPv6
            when = datetime.strptime(when_str, "%Y-%m-%d %H:%M:%S")
            errors.append((user, ip, when, line.strip()))
    return errors


def main():
    host = SERVERS["ftp"]
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

    new = save_errors("ftp", errors)
    print(f"\n[OK] {new} nouvelle(s) tentative(s) enregistrée(s) en base "
          f"({len(errors) - new} déjà présente(s)).")


if __name__ == "__main__":
    main()
