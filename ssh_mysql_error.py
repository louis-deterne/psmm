#!/usr/bin/env python3
"""recup les try d'accès refusé dans les logs MariaDB
et les enregistre dans la base psmm (table access_errors)."""


import hashlib
import re
import sys
from datetime import datetime
from config import SERVERS
from ssh_login_sudo import ssh_sudo
from ssh_mysql import get_connection

LOG_FILE = "/var/log/mysql/error.log"

# 2026-10-04 16:38:25 32 [Warning] access denied for user 'pirate'@'192.168.25.133' (using password: YES)
PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}:\d{2})\s+\d+\s+\[Warning\]\s+"
    r"Access denied for user '([^']*)'@'([^']*)'"
)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS access_errors (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    service      VARCHAR(10)  NOT NULL,
    username     VARCHAR(255) NOT NULL,
    ip           VARCHAR(64)  NOT NULL,
    attempt_time DATETIME     NOT NULL,
    raw_line     TEXT         NOT NULL,
    line_hash    CHAR(64)     NOT NULL UNIQUE,
    inserted_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_time (attempt_time),
    INDEX idx_service (service)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def parse_log(text):
    """retourne la liste des tentatives : (username, ip, datetime, ligne brute)."""
    errors = []
    for line in text.splitlines():
        m = PATTERN.search(line)
        if m:
            date, time, user, ip = m.groups()
            when = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")
            errors.append((user, ip, when, line.strip()))
    return errors


def save_errors(service, errors):
    """save les tentatives en base. Retourne le nombre de NOUVELLES lignes.

    toutes les lines de log a un hash qui lui est propre (line_hash) : donc pas de doublon si relancé (INSERT IGNORE).
    """
    rows = [
        (service, user, ip, when, line,
         hashlib.sha256(f"{service}|{line}".encode()).hexdigest())
        for user, ip, when, line in errors
    ]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE)
            if not rows:
                return 0
            cur.executemany(
                "INSERT IGNORE INTO access_errors "
                "(service, username, ip, attempt_time, raw_line, line_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s)", rows)
            return cur.rowcount
    finally:
        conn.close()


def main():
    host = SERVERS["db"]
    print(f"Lecture de {LOG_FILE} sur {host}...")
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

    new = save_errors("mysql", errors)
    print(f"\n[OK] {new} nouvelle(s) tentative(s) enregistrée(s) en base "
          f"({len(errors) - new} déjà présente(s)).")


if __name__ == "__main__":
    main()
