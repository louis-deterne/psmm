#!/usr/bin/env python3
"""check l'accès au server MariaDB/MySQL.

Test 1 : via SSH + sudo sur slm-db (service, version, bases)
Test 2 : connexion reseau directe à la base psmm avec le compte applicatif

fonction get_connection() est reutilisé par les jobs suivants.
"""
import sys
import pymysql
from config import SERVERS, DB_HOST, DB_NAME
from credentials import DB_USER, DB_PASSWORD
from ssh_login_sudo import ssh_sudo


def get_connection():
    """retourne une connexion à la base psmm."""
    return pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
                           database=DB_NAME, charset="utf8mb4",
                           connect_timeout=10, autocommit=True)


def test_ssh():
    host = SERVERS["db"]
    print(f"=== test 1 : SSH + sudo sur {host} ===")
    ok = True
    checks = [
        ("Service MariaDB", "systemctl is-active mariadb"),
        ("Version et bases", "mariadb -e 'SELECT VERSION(); SHOW DATABASES;'"),
    ]
    for label, cmd in checks:
        code, out, err = ssh_sudo(host, cmd)
        status = "ok" if code == 0 else "error"
        print(f"{status} {label}")
        print(out.strip() if code == 0 else err.strip())
        print()
        ok = ok and code == 0
    return ok


def test_network():
    print(f"=== test 2 : connexion reseau {DB_USER}@{DB_HOST}/{DB_NAME} ===")
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION(), CURRENT_USER(), DATABASE()")
            version, user, db = cur.fetchone()
        conn.close()
        print(f"connecté : MariaDB {version} | utilisateur {user} | base {db}")
        return True
    except pymysql.MySQLError as e:
        print(f"échec de connexion : {e}")
        return False


def main():
    ok_ssh = test_ssh()
    ok_net = test_network()
    print()
    if ok_ssh and ok_net:
        print("accès au serveur MariaDB verifié.")
        sys.exit(0)
    print("au moins un test a fail.")
    sys.exit(1)


if __name__ == "__main__":
    main()
