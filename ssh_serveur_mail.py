#!/usr/bin/env python3
"""envoie à l'admin un mail récap des try de connextion refusées de la veille (MariaDB, FTP, Web).

Usage : python3 ssh_serveur_mail.py              -> rapport d'hier
        python3 ssh_serveur_mail.py 2026-10-06   -> rapport d'un jour précis (tests)
"""


import html
import smtplib
import sys
from collections import Counter
from datetime import date, timedelta
from email.message import EmailMessage
from config import SMTP_HOST, SMTP_PORT, MAIL_TO
from credentials import MAIL_USER, MAIL_PASSWORD
from ssh_mysql import get_connection


def send_mail(subject, text, html_body=None, to=MAIL_TO):
    """envoie un mail via Gmail (STARTTLS). Version texte + HTML optionnelle."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = MAIL_USER
    msg["To"] = to
    msg.set_content(text)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.starttls()                       # chiffre la connexion avant le login
        smtp.login(MAIL_USER, MAIL_PASSWORD)
        smtp.send_message(msg)


def get_attempts(day):
    """eetourne les tentatives refusées du jour `day`."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT service, username, ip, attempt_time FROM access_errors "
                "WHERE attempt_time >= %s AND attempt_time < %s "
                "ORDER BY attempt_time",
                (day, day + timedelta(days=1)))
            return cur.fetchall()
    finally:
        conn.close()


def build_report(day, rows):
    """build du rapport du raw text en HTML."""
    counts = Counter(r[0] for r in rows)
    summary = " | ".join(f"{s} : {counts.get(s, 0)}" for s in ("mysql", "ftp", "web"))

    # Version texte
    lines = [f"Rapport PSMM - tentatives d'accès refusées le {day:%d/%m/%Y}",
             f"Total : {len(rows)}  ({summary})", ""]
    if rows:
        lines.append(f"{'Heure':<10}{'Service':<9}{'Compte':<22}IP")
        for service, user, ip, when in rows:
            lines.append(f"{when:%H:%M:%S}  {service:<9}{user:<22}{ip}")
    else:
        lines.append("Aucune tentative refusée.")
    text = "\n".join(lines)

    # Version HTML (html.escape : les noms d'users viennent d'attaquants !)
    cell = 'style="border:1px solid #ccc;padding:4px 8px"'
    table_rows = "".join(
        f"<tr><td {cell}>{when:%H:%M:%S}</td><td {cell}>{html.escape(service)}</td>"
        f"<td {cell}>{html.escape(user)}</td><td {cell}>{html.escape(ip)}</td></tr>"
        for service, user, ip, when in rows)
    html_body = f"""<html><body style="font-family:Arial,sans-serif">
<h2>Rapport PSMM - {day:%d/%m/%Y}</h2>
<p><b>{len(rows)}</b> tentative(s) d'accès refusée(s) &mdash; {html.escape(summary)}</p>
{"<table style='border-collapse:collapse'><tr>"
 f"<th {cell}>Heure</th><th {cell}>Service</th><th {cell}>Compte</th><th {cell}>IP</th></tr>"
 + table_rows + "</table>" if rows else "<p>Aucune tentative refusée.</p>"}
</body></html>"""
    return text, html_body


def main():
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today() - timedelta(days=1)
    rows = get_attempts(day)
    text, html_body = build_report(day, rows)
    print(text)
    subject = f"[PSMM] {len(rows)} tentative(s) d'accès refusée(s) le {day:%d/%m/%Y}"
    send_mail(subject, text, html_body)
    print(f"\n[OK] Mail envoyé à {MAIL_TO}")


if __name__ == "__main__":
    main()
