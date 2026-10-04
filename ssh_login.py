#!/usr/bin/env python3
"""se connecte en ssh à un server et exec une command shell."""


import sys
import paramiko
from config import SERVERS, SSH_USER, SSH_KEY


def ssh_exec(host, command):
    """Exec `command` sur `host` en SSH. return (code_retour, stdout, stderr)."""
    client = paramiko.SSHClient()
    client.load_system_host_keys()                      # usage ~/.ssh/known_hosts
    client.set_missing_host_key_policy(paramiko.RejectPolicy())  # deny en cas de serveur inconnu
    client.connect(hostname=host, username=SSH_USER,
                   key_filename=SSH_KEY, timeout=10)
    try:
        stdin, stdout, stderr = client.exec_command(command)
        out = stdout.read().decode()
        err = stderr.read().decode()
        code = stdout.channel.recv_exit_status()
        return code, out, err
    finally:
        client.close()


def main():
    server = sys.argv[1] if len(sys.argv) > 1 else "ftp"
    command = " ".join(sys.argv[2:]) or "df -h"

    if server not in SERVERS:
        print(f"Serveur inconnu : {server}. Choix possibles : {', '.join(SERVERS)}")
        sys.exit(1)

    host = SERVERS[server]
    print(f"[{server}] monitor@{host} $ {command}\n")
    code, out, err = ssh_exec(host, command)
    print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()
