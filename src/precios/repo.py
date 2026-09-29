import hashlib
import os
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .modelos import Oferta


def _conectar():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sesion_por_token(token: str) -> tuple[str, str] | None:
    with _conectar() as c:
        fila = c.execute(
            "SELECT t.slug, k.rol FROM api_tokens k JOIN tenants t ON t.id = k.tenant_id WHERE k.token_sha256 = %s",
            (hash_token(token),),
        ).fetchone()
    return (fila["slug"], fila["rol"]) if fila else None


def sesion_por_chat(chat_id: int) -> tuple[str, str] | None:
    with _conectar() as c:
        fila = c.execute(
            "SELECT t.slug, ch.rol FROM telegram_chats ch JOIN tenants t ON t.id = ch.tenant_id WHERE ch.chat_id = %s",
            (chat_id,),
        ).fetchone()
    return (fila["slug"], fila["rol"]) if fila else None


def guardar_lista(tenant: str, proveedor: str, fecha: date, ofertas: list[dict], texto_original: str) -> int:
    with _conectar() as c:
        tenant_id = c.execute("SELECT id FROM tenants WHERE slug = %s", (tenant,)).fetchone()["id"]
        # Recargar el mismo proveedor y día reemplaza la lista entera (el cascade borra sus ofertas).
        c.execute(
            "DELETE FROM listas_proveedor WHERE tenant_id = %s AND proveedor = %s AND fecha = %s",
            (tenant_id, proveedor, fecha),
        )
        lista_id = c.execute(
            "INSERT INTO listas_proveedor (tenant_id, proveedor, fecha, texto_original) VALUES (%s, %s, %s, %s) RETURNING id",
            (tenant_id, proveedor, fecha, texto_original),
        ).fetchone()["id"]
        with c.cursor() as cur:
            cur.executemany(
                """INSERT INTO ofertas (lista_id, categoria, condicion, modelo, capacidad, ram_rom, color,
                                        bateria, sufijos, costo, stock, precios_volumen)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (lista_id, o["categoria"], o["condicion"], o["modelo"], o["capacidad"], o["ram_rom"], o["color"],
                     o["bateria"], o["sufijos"], o["costo"], o["stock"],
                     Jsonb({str(k): v for k, v in o["precios_volumen"].items()}))
                    for o in ofertas
                ],
            )
    return lista_id


def ultimas_ofertas(tenant: str, hasta: date) -> list[Oferta]:
    """La lista más reciente de cada proveedor hasta esa fecha. Si está vencida lo decide el servicio."""
    with _conectar() as c:
        filas = c.execute(
            """WITH ultimas AS (
                   SELECT DISTINCT ON (l.proveedor) l.id, l.proveedor, l.fecha
                   FROM listas_proveedor l JOIN tenants t ON t.id = l.tenant_id
                   WHERE t.slug = %s AND l.fecha <= %s
                   ORDER BY l.proveedor, l.fecha DESC)
               SELECT u.proveedor, u.fecha, o.* FROM ultimas u JOIN ofertas o ON o.lista_id = u.id""",
            (tenant, hasta),
        ).fetchall()
    return [
        Oferta(
            proveedor=f["proveedor"], fecha_lista=f["fecha"], categoria=f["categoria"], condicion=f["condicion"],
            modelo=f["modelo"], capacidad=f["capacidad"], ram_rom=f["ram_rom"], color=f["color"],
            bateria=f["bateria"], sufijos=list(f["sufijos"]), stock=f["stock"],
            costo=float(f["costo"]) if f["costo"] is not None else None,
            precios_volumen={int(k): v for k, v in f["precios_volumen"].items()},
        )
        for f in filas
    ]


def historial(tenant: str, modelo: str, dias: int) -> list[dict]:
    with _conectar() as c:
        filas = c.execute(
            """SELECT l.fecha, l.proveedor, o.condicion, o.modelo, o.capacidad, o.color, o.bateria, o.costo, o.stock
               FROM ofertas o
               JOIN listas_proveedor l ON l.id = o.lista_id
               JOIN tenants t ON t.id = l.tenant_id
               WHERE t.slug = %s AND o.modelo ILIKE %s AND l.fecha >= %s
               ORDER BY o.modelo, o.capacidad, l.fecha""",
            (tenant, f"%{modelo}%", date.today() - timedelta(days=dias)),
        ).fetchall()
    return [{**f, "fecha": f["fecha"].isoformat(), "costo": float(f["costo"]) if f["costo"] is not None else None} for f in filas]
