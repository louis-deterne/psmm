#!/usr/bin/env python3
"""saves horodatée de la base psmm sur slm-db,avec conservation des 7 dernieres sauvegardes, schedule toutes les 3h (cron). """


import sys
from datetime import datetime
from config import SERVERS, DB_NAME
from ssh_login_sudo import ssh_sudo

BACKUP_DIR = "/var/backups/psmm"
KEEP = 7  # nombre de sauvegardes conservées


def backup():
    host = SERVERS["db"]
    stamp = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%S")
    sql_file = f"{BACKUP_DIR}/{DB_NAME}_{stamp}.sql"
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Sauvegarde de '{DB_NAME}' sur {host}")

    # 1. dump + compression (dossier en 700 : root only pour la lecture des saves)
    cmd = (f"mkdir -p {BACKUP_DIR} && chmod 700 {BACKUP_DIR} && "
           f"mariadb-dump --single-transaction --routines --databases {DB_NAME} > {sql_file} && "
           f"gzip {sql_file} && gzip -t {sql_file}.gz")
    code, out, err = ssh_sudo(host, cmd)
    if code != 0:
        print(f"[ERREUR] Sauvegarde échouée : {err.strip()}")
        return False
    print(f"[OK] {sql_file}.gz créé")

    # 2. rotation : garde les KEEP plus récentes, supprime les autres
    cmd = (f"ls -1t {BACKUP_DIR}/{DB_NAME}_*.sql.gz | tail -n +{KEEP + 1} | xargs -r rm -v -- ; "
           f"ls -lh {BACKUP_DIR}")
    code, out, err = ssh_sudo(host, cmd)
    print(out.strip())
    return True


if __name__ == "__main__":
    sys.exit(0 if backup() else 1)
