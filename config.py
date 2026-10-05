"""main config du projet PSMM - slm jobs."""
import os

# servers (les noms sont résolus via /etc/hosts la vm slm-admin)
SERVERS = {
    "ftp": "slm-ftp",
    "web": "slm-web",
    "db":  "slm-db",
}

# connection SSH
SSH_USER = "monitor"
SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")




# Base de données
DB_HOST = "slm-db"
DB_NAME = "psmm"
