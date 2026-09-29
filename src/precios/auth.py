"""Quién llama y de qué negocio es. Tres caminos:

1. Token de API del tenant (Claude Desktop, integraciones): `Authorization: Bearer <token>`.
2. n8n por Telegram: token de servicio + `X-Chat-Id`; el chat define el tenant y el rol.
3. Desarrollo: DEV_TOKENS="token:tenant:rol,..." sin base de datos.
"""

import hmac
import os
from collections.abc import Mapping
from dataclasses import dataclass

from . import repo


@dataclass(frozen=True)
class Sesion:
    tenant: str
    rol: str  # duenio | empleado


def _tokens_dev() -> dict[str, Sesion]:
    tokens = {}
    for entrada in filter(None, os.environ.get("DEV_TOKENS", "").split(",")):
        token, tenant, rol = entrada.strip().split(":")
        tokens[token] = Sesion(tenant, rol)
    return tokens


def resolver(headers: Mapping[str, str]) -> Sesion | None:
    token = (headers.get("authorization") or "").removeprefix("Bearer ").strip()
    if not token:
        return None

    if token in (dev := _tokens_dev()):
        return dev[token]

    servicio = os.environ.get("SERVICE_TOKEN", "")
    if servicio and hmac.compare_digest(token, servicio):
        chat = headers.get("x-chat-id", "")
        fila = repo.sesion_por_chat(int(chat)) if chat.lstrip("-").isdigit() else None
        return Sesion(*fila) if fila else None

    if not os.environ.get("DATABASE_URL"):
        return None
    fila = repo.sesion_por_token(token)
    return Sesion(*fila) if fila else None
