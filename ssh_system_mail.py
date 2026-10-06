#!/usr/bin/env python3
"""monitoring CPU/RAM/disque (Job 11) + mail d'alerte à
l'administrateur si un seuil est dépassé ou si un server est injoignable.

Job 13 : au maximum UN mail par heure. """


import argparse
from datetime import datetime, timedelta
from config import SERVERS
from ssh_mysql import get_connection
from ssh_system_status import collect_all, save_status, print_results
from ssh_serveur_mail import send_mail

# ============ Seuils d'alerte (en %) ============
SEUIL_CPU = 70
SEUIL_DISK = 90
SEUIL_RAM = 80
# ============ Anti-spam : délai minimum entre 2 mails ============
MAIL_INTERVAL_MIN = 60
# =================================================================

LABELS = {"cpu": "CPU", "ram": "RAM", "disk": "Disque"}

CREATE_ALERT_TABLE = """
CREATE TABLE IF NOT EXISTS alert_log (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME   NOT NULL,
    message    TEXT       NOT NULL,
    mail_sent  TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def check_alerts(results, seuils):
    """retourne la liste des dépassements : (serveur, ressource, valeur, seuil)."""
    alerts = []
    for name, cpu, ram, disk in results:
        for key, value in (("cpu", cpu), ("ram", ram), ("disk", disk)):
            if value > seuils[key]:
                alerts.append((name, key, value, seuils[key]))
    return alerts


def build_alert(alerts, down):
    """Construit le sujet et le texte du mail d'alerte."""
    lines = [f"Alerte PSMM - {datetime.now():%d/%m/%Y %H:%M}", ""]
    for name in down:
        lines.append(f"- {name} ({SERVERS[name]}) : SERVEUR INJOIGNABLE")
    for name, key, value, seuil in alerts:
        lines.append(f"- {name} : {LABELS[key]} à {value}% (seuil {seuil}%)")
    servers = sorted(set(down) | {a[0] for a in alerts})
    return f"[PSMM][ALERTE] Problème sur {', '.join(servers)}", "\n".join(lines)


def process_alert(subject, text, interval_min):
    """Envoie le mail seulement si le dernier envoi date de plus de `interval_min`
    minutes. L'alerte est historisée dans alert_log dans tous les cas."""
    now = datetime.now()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_ALERT_TABLE)
            cur.execute("SELECT MAX(created_at) FROM alert_log WHERE mail_sent = 1")
            last = cur.fetchone()[0]

            if last is not None and now - last < timedelta(minutes=interval_min):
                next_ok = last + timedelta(minutes=interval_min)
                print(f"[INFO] Mail retenu (max 1 par {interval_min} min) : dernier envoi "
                      f"à {last:%H:%M}, prochain possible à {next_ok:%H:%M}.")
                sent = False
            else:
                cur.execute("SELECT COUNT(*) FROM alert_log "
                            "WHERE mail_sent = 0 AND created_at > %s",
                            (last or datetime(1970, 1, 1),))
                held = cur.fetchone()[0]
                if held:
                    text += (f"\n\n{held} autre(s) alerte(s) détectée(s) depuis le dernier mail "
                             f"(retenue(s) pour limiter à 1 mail/heure, voir la table alert_log).")
                try:
                    send_mail(subject, text)
                    sent = True
                    print("[ALERTE] Mail envoyé à l'administrateur.")
                except Exception as e:
                    sent = False
                    print(f"[ERREUR] Envoi du mail impossible : {e}")

            cur.execute("INSERT INTO alert_log (created_at, message, mail_sent) "
                        "VALUES (%s, %s, %s)", (now, text, int(sent)))
            return sent
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Monitoring + alertes mail (max 1/heure)")
    parser.add_argument("--cpu", type=float, default=SEUIL_CPU, help="seuil CPU en %%")
    parser.add_argument("--ram", type=float, default=SEUIL_RAM, help="seuil RAM en %%")
    parser.add_argument("--disk", type=float, default=SEUIL_DISK, help="seuil disque en %%")
    parser.add_argument("--interval", type=int, default=MAIL_INTERVAL_MIN,
                        help="délai minimum entre 2 mails, en minutes")
    args = parser.parse_args()
    seuils = {"cpu": args.cpu, "ram": args.ram, "disk": args.disk}

    results = collect_all()
    print_results(results)
    save_status(results)

    alerts = check_alerts(results, seuils)
    down = [n for n in SERVERS if n not in {r[0] for r in results}]

    print(f"\nSeuils : CPU {seuils['cpu']}% | RAM {seuils['ram']}% | Disque {seuils['disk']}%")
    if alerts or down:
        subject, text = build_alert(alerts, down)
        print(text)
        process_alert(subject, text, args.interval)
    else:
        print("[OK] Aucun seuil dépassé, pas de mail.")


if __name__ == "__main__":
    main()
