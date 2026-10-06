#!/usr/bin/env python3
"""Recup l'état RAM / CPU / disque des servers, l'enregistre
dans la db psmm (table system_status) et ne garde que les dernières 72h."""



import sys
from datetime import datetime
from config import SERVERS
from ssh_login import ssh_exec
from ssh_mysql import get_connection

RETENTION_HOURS = 72

# Pas de sudo : /proc et df sont lisibles sans privilèges (moindre privilège)
STATUS_CMD = ("head -1 /proc/stat; sleep 1; head -1 /proc/stat; "
              "grep -E '^(MemTotal|MemAvailable):' /proc/meminfo; "
              "df -P / | tail -1")

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS system_status (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    server      VARCHAR(20)  NOT NULL,
    cpu_pct     DECIMAL(5,1) NOT NULL,
    ram_pct     DECIMAL(5,1) NOT NULL,
    disk_pct    DECIMAL(5,1) NOT NULL,
    measured_at DATETIME     NOT NULL,
    INDEX idx_server_time (server, measured_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def _cpu_times(line):
    """Ligne 'cpu ...' de /proc/stat -> (temps en idle, temps total)."""
    v = [int(x) for x in line.split()[1:9]]
    return v[3] + v[4], sum(v)


def get_status(host):
    """retourne (cpu %, ram %, disque %) du serveur `host`."""
    code, out, err = ssh_exec(host, STATUS_CMD)
    if code != 0:
        raise RuntimeError(err.strip())
    lines = out.strip().splitlines()

    idle1, total1 = _cpu_times(lines[0])
    idle2, total2 = _cpu_times(lines[1])
    cpu = 100 * (1 - (idle2 - idle1) / (total2 - total1)) if total2 > total1 else 0.0

    mem = {l.split(":")[0]: int(l.split()[1]) for l in lines[2:4]}
    ram = 100 * (1 - mem["MemAvailable"] / mem["MemTotal"])

    disk = float(lines[4].split()[4].rstrip("%"))
    return round(cpu, 1), round(ram, 1), round(disk, 1)


def collect_all():
    """mesure tous les servers. tetourne [(nom, cpu, ram, disque), ...]."""
    results = []
    for name, host in SERVERS.items():
        try:
            results.append((name, *get_status(host)))
        except Exception as e:
            print(f"[ERREUR] {name} ({host}) injoignable : {e}")
    return results


def save_status(results):
    """save les mesures et purge celles de plus de 72h.
    retourne le nombre de mesures supprimées."""
    now = datetime.now()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE)
            if results:
                cur.executemany(
                    "INSERT INTO system_status (server, cpu_pct, ram_pct, disk_pct, measured_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    [(*r, now) for r in results])
            cur.execute("DELETE FROM system_status WHERE measured_at < NOW() - INTERVAL %s HOUR",
                        (RETENTION_HOURS,))
            return cur.rowcount
    finally:
        conn.close()


def print_results(results):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] État des serveurs")
    print(f"{'Serveur':<10}{'CPU':>8}{'RAM':>8}{'Disque':>9}")
    print("-" * 35)
    for name, cpu, ram, disk in results:
        print(f"{name:<10}{cpu:>7}%{ram:>7}%{disk:>8}%")


def main():
    results = collect_all()
    print_results(results)
    purged = save_status(results)
    print(f"\n[OK] {len(results)} mesure(s) enregistrée(s), "
          f"{purged} mesure(s) de plus de {RETENTION_HOURS}h supprimée(s).")
    sys.exit(0 if len(results) == len(SERVERS) else 1)


if __name__ == "__main__":
    main()
