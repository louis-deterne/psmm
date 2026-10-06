#!/usr/bin/env python3
"""se connect en SSH a un serveur et exec une commande en sudo.

Réutilise ssh_exec() du Job 03 (ssh_login.py).
Usage : python3 ssh_login_sudo.py [ftp|web|db] [commande...]
Exemple : python3 ssh_login_sudo.py web tail -n 5 /var/log/nginx/error.log
"""
import shlex
import sys
from config import SERVERS
from credentials import SUDO_PASSWORD
from ssh_login import ssh_exec


def ssh_sudo(host, command, timeout=30):
    """Exec `command` en root sur `host` via sudo. R-> (code, stdout, stderr).

    sudo -S   : lit le mdp sur l'entry standard (envoyé par ssh_exec)
    -p ''     : delete le message "[sudo] password for monitor:"
    sh -c     : permet d'utiliser des pipes (|) ou redirect dans la commande
    """
    sudo_cmd = f"sudo -S -p '' sh -c {shlex.quote(command)}"
    return ssh_exec(host, sudo_cmd, input_data=SUDO_PASSWORD, timeout=timeout)


def main():
    server = sys.argv[1] if len(sys.argv) > 1 else "ftp"
    command = " ".join(sys.argv[2:]) or "whoami"

    if server not in SERVERS:
        print(f"serveur inconnu : {server}. choix disponibles : {', '.join(SERVERS)}")
        sys.exit(1)

    host = SERVERS[server]
    print(f"[{server}] monitor@{host} # sudo {command}\n")
    code, out, err = ssh_sudo(host, command)
    print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()
