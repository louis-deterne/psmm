#!/usr/bin/env python3
"""se connecte en SSH à un server et exec une commande shell."""


import sys
import paramiko
from config import SERVERS, SSH_USER, SSH_KEY


def ssh_exec(host, command, input_data=None, timeout=30):
    """Exécute `command` sur `host` en SSH. R-> (code_retour, stdout, stderr).

    input_data : texte optionnel envoyé sur l'entrée standard de la commande
                 (utilisé par le Job 04 pour share le mot de passe sudo).
    """
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(hostname=host, username=SSH_USER,
                   key_filename=SSH_KEY, timeout=10)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        if input_data is not None:
            stdin.write(input_data + "\n")
            stdin.flush()
            stdin.channel.shutdown_write()
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
        print(f"server inconnu : {server}. choix disponibles : {', '.join(SERVERS)}")
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
