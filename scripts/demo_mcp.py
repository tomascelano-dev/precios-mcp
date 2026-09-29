"""Recorre el servidor por MCP como lo haría Claude, contra la config de ejemplo.

    DEV_TOKENS="demo:demo:duenio" DATABASE_URL=... uvicorn precios.main:app --port 8765
    python scripts/demo_mcp.py

La lista del proveedor llega desordenada (typos, colores abreviados, un precio por volumen mal
tipeado, un usado con batería baja). En un uso real Claude la estructura desde el texto; acá va ya
estructurada para que la demo no dependa de un modelo, y se ve qué corrige el núcleo por su cuenta.
"""

import asyncio
import json
import os
from datetime import date

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

URL = os.environ.get("PRECIOS_MCP_URL", "http://localhost:8765/mcp/")
TOKEN = os.environ.get("PRECIOS_TOKEN", "demo")

TEXTO_PROVEEDOR = """LISTA HOY
IPHONE 16 128 Black/Mid 800
IPHONE 16 128 Lavander 800
IPHONE 16 PRO 256 Desert 1010
S25 FE 8/256 Ultra 575 · x3 665 · x5 560
USADO 13 128 Midnight bat 76% 300"""

OFERTAS = [
    {"categoria": "iphone", "condicion": "nuevo", "modelo": "iPhone 16", "capacidad": "128GB", "color": "Black", "costo": 800},
    {"categoria": "iphone", "condicion": "nuevo", "modelo": "iPhone 16", "capacidad": "128GB", "color": "Mid", "costo": 800},
    {"categoria": "iphone", "condicion": "nuevo", "modelo": "iPhone 16", "capacidad": "128GB", "color": "Lavander", "costo": 800},
    {"categoria": "iphone", "condicion": "nuevo", "modelo": "iPhone 16 Pro", "capacidad": "256GB", "color": "Desert", "costo": 1010},
    {"categoria": "samsung", "condicion": "nuevo", "modelo": "Galaxy S25 FE", "ram_rom": "8/256", "color": "Ultra",
     "costo": 575, "precios_volumen": {"3": 665, "5": 560}},
    {"categoria": "iphone", "condicion": "usado", "modelo": "iPhone 13", "capacidad": "128GB", "color": "Midnight",
     "bateria": 76, "costo": 300},
]


def contenido(resultado) -> dict:
    # El SDK 2.x pasó los campos a snake_case (antes isError / structuredContent).
    if resultado.is_error:
        raise SystemExit(f"error de la tool: {resultado.content[0].text}")
    return resultado.structured_content or json.loads(resultado.content[0].text)


async def main() -> None:
    http = create_mcp_http_client(headers={"Authorization": f"Bearer {TOKEN}"})
    async with http, streamable_http_client(URL, http_client=http) as (leer, escribir):
        async with ClientSession(leer, escribir) as sesion:
            await sesion.initialize()
            tools = await sesion.list_tools()
            print("tools:", ", ".join(t.name for t in tools.tools))

            reglas = contenido(await sesion.call_tool("reglas_del_negocio", {}))
            print(f"negocio: {reglas['negocio']} · categorías: {', '.join(reglas['categorias'])}\n")

            carga = contenido(await sesion.call_tool("cargar_lista_proveedor", {
                "proveedor": "mayorista", "fecha": date.today().isoformat(),
                "ofertas": OFERTAS, "texto_original": TEXTO_PROVEEDOR,
            }))
            print(f"cargada la lista {carga['lista_id']} con {carga['ofertas_guardadas']} ofertas\n")

            listas = contenido(await sesion.call_tool("generar_listas", {}))
            for texto in listas["listas"].values():
                print(texto, end="\n\n")
            print("alertas:")
            for a in listas["alertas"]:
                print(f"  [{a['tipo']}] {a['detalle']}")


if __name__ == "__main__":
    asyncio.run(main())
