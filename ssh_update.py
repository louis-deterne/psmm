#!/usr/bin/env python3
"""Mise à jour des servers.

Pour chaque server : connexion à ALCASAR, vérification des mises à jour,
installation, détection d'un redémarrage nécessaire, déconnexion d'ALCASAR.
Un mail est envoyé à l'administrateur si un redémarrage est nécessaire
ou en cas d'erreur.
"""
from datetime import datetime
from config import SERVERS, ALCASAR_ENABLED
from ssh_login import ssh_exec
from ssh_login_sudo import ssh_sudo
from ssh_serveur_mail import send_mail

UPGRADE_CMD = ("DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l "
               "apt-get -y -q -o Dpkg::Options::=--force-confdef "
               "-o Dpkg::Options::=--force-confold full-upgrade")


# ---------- ALCASAR (portail captif) : à compléter à l'école ----------
def alcasar_login(host):
    """Auth le server `host` sur le portail ALCASAR."""
    if not ALCASAR_ENABLED:
        return
    raise NotImplementedError("Connexion ALCASAR à configurer (étape 2 du Job 14)")


def alcasar_logout(host):
    """Déconnecte le serveur `host` du portail ALCASAR."""
    if not ALCASAR_ENABLED:
        return
    raise NotImplementedError("Déconnexion ALCASAR à configurer (étape 2 du Job 14)")
# -----------------------------------------------------------------------


def internet_ok(host):
    """Vérifie que le serveur accède aux dépôts Debian (sinon : portail captif ?)."""
    code, out, _ = ssh_exec(host, "curl -s -o /dev/null -w '%{http_code}' "
                                  "--max-time 10 http://deb.debian.org/debian/")
    return out.strip() == "200"


def reboot_status(host):
    """Retourne (redémarrage du serveur nécessaire ?, services à redémarrer)."""
    _, out, _ = ssh_sudo(host, "needrestart -b -r l 2>/dev/null", timeout=120)
    reboot, services = False, []
    for line in out.splitlines():
        if line.startswith("NEEDRESTART-KSTA:"):
            # 1 = noyau à jour ; 2 ou 3 = nouveau noyau installé -> redémarrage
            reboot = line.split(":")[1].strip() in ("2", "3")
        elif line.startswith("NEEDRESTART-SVC:"):
            services.append(line.split(":", 1)[1].strip())
    return reboot, services


def update_server(host):
    """Met à jour un serveur. Retourne un dict avec le résultat."""
    r = {"error": None, "packages": [], "reboot": False, "services": []}
    if not internet_ok(host):
        r["error"] = "pas d'accès aux dépôts Debian (ALCASAR non connecté ?)"
        return r

    code, _, err = ssh_sudo(host, "apt-get update -qq", timeout=300)
    if code != 0:
        r["error"] = f"apt-get update : {err.strip()[-300:]}"
        return r

    _, out, _ = ssh_sudo(host, "LC_ALL=C apt list --upgradable 2>/dev/null | tail -n +2")
    r["packages"] = [l.split("/")[0] for l in out.splitlines() if "/" in l]

    if r["packages"]:
        code, _, err = ssh_sudo(host, UPGRADE_CMD, timeout=1800)
        if code != 0:
            r["error"] = f"apt-get full-upgrade : {err.strip()[-300:]}"
            return r

    r["reboot"], r["services"] = reboot_status(host)
    return r


def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Mise à jour des serveurs")
    report, notify = [], False

    for name, host in SERVERS.items():
        print(f"\n=== {name} ({host}) ===")
        try:
            alcasar_login(host)
            r = update_server(host)
        except Exception as e:
            r = {"error": str(e), "packages": [], "reboot": False, "services": []}
        finally:
            try:
                alcasar_logout(host)
            except Exception as e:
                print(f"[ERREUR] Déconnexion ALCASAR : {e}")

        if r["error"]:
            line = f"- {name} : ERREUR - {r['error']}"
            notify = True
        else:
            line = f"- {name} : {len(r['packages'])} paquet(s) mis à jour"
            if r["packages"]:
                line += f" ({', '.join(r['packages'][:15])}{'...' if len(r['packages']) > 15 else ''})"
            if r["reboot"]:
                line += "\n    -> REDÉMARRAGE NÉCESSAIRE (nouveau noyau)"
                notify = True
            if r["services"]:
                line += f"\n    -> services à redémarrer : {', '.join(r['services'])}"
        print(line)
        report.append(line)

    if notify:
        text = (f"Rapport de mise à jour PSMM - {datetime.now():%d/%m/%Y %H:%M}\n\n"
                + "\n".join(report))
        send_mail("[PSMM][MAJ] Action requise sur les serveurs", text)
        print("\n[ALERTE] Redémarrage nécessaire ou erreur : mail envoyé à l'administrateur.")
    else:
        print("\n[OK] Serveurs à jour, aucun redémarrage nécessaire.")


if __name__ == "__main__":
    main()
