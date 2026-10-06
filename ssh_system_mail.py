#!/usr/bin/env python3
"""reprend le Job 11 (mesure CPU/RAM/disque) et envoie
un mail d'alerte à l'administrateur si un seuil est dépassé ou si un serveur
est injoignable. Planifié toutes les 5 minutes (cron)."""


import argparse
from datetime import datetime
from config import SERVERS
from ssh_system_status import collect_all, save_status, print_results
from ssh_serveur_mail import send_mail

# ============ Seuils d'alerte (en %) - à modifier ici ============
SEUIL_CPU = 70
SEUIL_DISK = 90
SEUIL_RAM = 80
# =================================================================

LABELS = {"cpu": "CPU", "ram": "RAM", "disk": "Disque"}


def check_alerts(results, seuils):
    """Retourne la liste des dépassements : (serveur, ressource, valeur, seuil)."""
    alerts = []
    for name, cpu, ram, disk in results:
        for key, value in (("cpu", cpu), ("ram", ram), ("disk", disk)):
            if value > seuils[key]:
                alerts.append((name, key, value, seuils[key]))
    return alerts


def send_alert(alerts, down):
    """Envoie le mail d'alerte à l'administrateur."""
    lines = [f"Alerte PSMM - {datetime.now():%d/%m/%Y %H:%M}", ""]
    for name in down:
        lines.append(f"- {name} ({SERVERS[name]}) : SERVEUR INJOIGNABLE")
    for name, key, value, seuil in alerts:
        lines.append(f"- {name} : {LABELS[key]} à {value}% (seuil {seuil}%)")
    text = "\n".join(lines)
    servers = sorted(set(down) | {a[0] for a in alerts})
    send_mail(f"[PSMM][ALERTE] Problème sur {', '.join(servers)}", text)
    return text


def main():
    parser = argparse.ArgumentParser(description="Monitoring + alertes mail")
    parser.add_argument("--cpu", type=float, default=SEUIL_CPU, help="seuil CPU en %%")
    parser.add_argument("--ram", type=float, default=SEUIL_RAM, help="seuil RAM en %%")
    parser.add_argument("--disk", type=float, default=SEUIL_DISK, help="seuil disque en %%")
    args = parser.parse_args()
    seuils = {"cpu": args.cpu, "ram": args.ram, "disk": args.disk}

    results = collect_all()
    print_results(results)
    save_status(results)

    alerts = check_alerts(results, seuils)
    down = [n for n in SERVERS if n not in {r[0] for r in results}]

    print(f"\nSeuils : CPU {seuils['cpu']}% | RAM {seuils['ram']}% | Disque {seuils['disk']}%")
    if alerts or down:
        print(send_alert(alerts, down))
        print("[ALERTE] Mail envoyé à l'administrateur.")
    else:
        print("[OK] Aucun seuil dépassé, pas de mail.")


if __name__ == "__main__":
    main()
