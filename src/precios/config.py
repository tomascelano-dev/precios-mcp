import json
import os
import re
from pathlib import Path

CONFIG_DIR = Path(
    os.environ.get("PRECIOS_CONFIG_DIR", Path(__file__).resolve().parents[2] / "config" / "tenants")
)


def cargar_config(tenant: str) -> dict:
    # El slug arma una ruta de archivo: sin esto, "../x" leería fuera de la carpeta.
    if not re.fullmatch(r"[a-z0-9_-]+", tenant):
        raise ValueError(f"tenant inválido: {tenant!r}")
    return json.loads((CONFIG_DIR / f"{tenant}.json").read_text(encoding="utf-8"))
