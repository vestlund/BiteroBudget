"""Var databasen och säkerhetskopiorna ligger.

Databasen ska inte ligga i en OneDrive-synkad mapp: SQLite kan skadas om OneDrive synkar filen medan
programmet kör. Därför ligger den som standard i %USERPROFILE%\\bitero-budget-data (Windows) eller
~/bitero-budget-data (Mac/Linux). Vill du ha en annan plats: sätt miljövariabeln BUDGET_DATA_DIR.

Säkerhetskopior sparas i datamappen/backups om inte BUDGET_BACKUP_DIR är satt.
"""

import os
from pathlib import Path

DB_NAMN = "budget.sqlite3"


def hitta_datamapp() -> Path:
    data_dir = Path(os.environ.get("BUDGET_DATA_DIR") or Path.home() / "bitero-budget-data")
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def hitta_backupmapp(data_dir: Path) -> Path:
    if satt := os.environ.get("BUDGET_BACKUP_DIR"):
        return Path(satt)
    return data_dir / "backups"
