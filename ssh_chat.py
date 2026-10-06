#!/usr/bin/env python3
"""envoie periodiquement dans un space google ghat l'état des serveurs
(CPU/RAM/disque), les try d'accès refusées et les alertes des 24 dernières heures.
"""
import sys
from datetime import datetime
import requests
from config import SERVERS
from credentials import CHAT_WEBHOOK_URL
from ssh_mysql import get_connection
from ssh_system_status import collect_all
from ssh_system_mail import SEUIL_CPU, SEUIL_RAM, SEUIL_DISK


def send_chat(text):
    """post un message dans le space google chat via le webhook."""
    r = requests.post(CHAT_WEBHOOK_URL, json={"text": text}, timeout=15)
    r.raise_for_status()


def stats_24h():
    """stats des 24 dernières heures depuis la base psmm."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT service, COUNT(*) FROM access_errors "
                        "WHERE attempt_time >= NOW() - INTERVAL 24 HOUR GROUP BY service")
            errors = dict(cur.fetchall())
            cur.execute("SELECT ip, COUNT(*) AS n FROM access_errors "
                        "WHERE attempt_time >= NOW() - INTERVAL 24 HOUR "
                        "GROUP BY ip ORDER BY n DESC LIMIT 3")
            top_ips = cur.fetchall()
            cur.execute("SELECT COUNT(*), COALESCE(SUM(mail_sent), 0) FROM alert_log "
                        "WHERE created_at >= NOW() - INTERVAL 24 HOUR")
            alerts, mails = cur.fetchone()
    finally:
        conn.close()
    return errors, top_ips, int(alerts), int(mails)


def build_message():
    lines = [f"🖥️apport PSMM - groupe slm* ({datetime.now():%d/%m/%Y %H:%M})",
             "", "*État des serveurs*"]

    results = collect_all()
    for name, cpu, ram, disk in results:
        warn = cpu > SEUIL_CPU or ram > SEUIL_RAM or disk > SEUIL_DISK
        icon = "no" if warn else "no"
        lines.append(f"{icon} {name} : CPU {cpu}% | RAM {ram}% | Disque {disk}%")
    for name in SERVERS:
        if name not in {r[0] for r in results}:
            lines.append(f"ALRT {name} : INJOIGNABLE")

    errors, top_ips, alerts, mails = stats_24h()
    lines += ["", "*Tentatives d'accès refusées (24h)*",
              f"Total : {sum(errors.values())}  —  MariaDB {errors.get('mysql', 0)} | "
              f"FTP {errors.get('ftp', 0)} | Web {errors.get('web', 0)}"]
    if top_ips:
        lines.append("IP les plus actives : "
                     + ", ".join(f"`{ip}` ({n})" for ip, n in top_ips))

    lines += ["", f"*Alertes (24h)* : {alerts} détectée(s), {mails} mail(s) envoyé(s)"]
    return "\n".join(lines)


def main():
    message = build_message()
    print(message)
    try:
        send_chat(message)
    except requests.RequestException as e:
        print(f"\n[ERREUR] Envoi Google Chat impossible : {e}")
        sys.exit(1)
    print("\n[OK] Message envoyé dans le Space Google Chat.")


if __name__ == "__main__":
    main()
