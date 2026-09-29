"""Las mismas operaciones que la API, como tools MCP. Acá Claude hace lo difuso (leer la lista del
proveedor tal como llegó y estructurarla); las cuentas las hace siempre el núcleo."""

import os
from datetime import date

import anyio
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from . import auth, operaciones
from .auth import Sesion
from .operaciones import CargaLista, OfertaIn

mcp = MCPServer("precios")

# Protección contra DNS rebinding: el SDK por defecto solo acepta Host localhost, lo que rechaza a n8n
# (llega como precios-api:8000) y al dominio público. Se listan los hosts válidos por entorno.
_HOSTS = os.environ.get("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*,precios-api:*").split(",")


def crear_app():
    return mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[h.strip() for h in _HOSTS],
            allowed_origins=[f"http://{h.strip()}" for h in _HOSTS] + [f"https://{h.strip()}" for h in _HOSTS],
        ),
    )


def _sesion(ctx: Context) -> Sesion:
    request = ctx.request_context.request
    s = auth.resolver(request.headers) if request is not None else None
    if s is None:
        raise ToolError("Token inválido o ausente")
    return s


async def _correr(fn, *args):
    # Solo el mensaje de un ToolError llega al modelo; cualquier otra excepción se ve como un
    # "Error executing tool" genérico y Claude no puede explicarle al usuario qué pasó.
    try:
        return await anyio.to_thread.run_sync(fn, *args)
    except (PermissionError, ValueError) as e:
        raise ToolError(str(e)) from e


@mcp.tool()
async def reglas_del_negocio(ctx: Context) -> dict:
    """Categorías, condiciones, proveedores y listas válidos del negocio. Llamarla ANTES de
    cargar_lista_proveedor para clasificar cada producto con una categoría existente."""
    s = _sesion(ctx)
    return await _correr(operaciones.reglas, s)


@mcp.tool()
async def cargar_lista_proveedor(
    proveedor: str, fecha: date, ofertas: list[OfertaIn], ctx: Context, texto_original: str = ""
) -> dict:
    """Guarda la lista de un proveedor ya estructurada.

    - Una oferta por modelo + capacidad + color: si el proveedor agrupa colores con un precio, separarlos.
    - costo = precio unitario del proveedor en USD; los precios por cantidad van en precios_volumen.
    - Si el proveedor no declara precio, costo = null (el núcleo lo excluye).
    - No corregir typos ni abreviaturas de color, no aplicar markup: eso lo hace el núcleo.
    - fecha = la fecha que figura en la lista del proveedor, no la de hoy.
    - Pasar el texto original completo en texto_original.
    Recargar el mismo proveedor y fecha reemplaza la lista anterior."""
    s = _sesion(ctx)
    carga = CargaLista(proveedor=proveedor, fecha=fecha, ofertas=ofertas, texto_original=texto_original)
    return await _correr(operaciones.cargar, s, carga)


@mcp.tool()
async def generar_listas(ctx: Context, fecha: date | None = None, interna: bool = False) -> dict:
    """Listas de venta en formato WhatsApp con markup aplicado, más las alertas del día
    (precios anómalos, categorías sin regla, garantías mezcladas, usados dominados por tester...).
    interna=True agrega el proveedor de cada línea (solo dueño). Mostrar las alertas al usuario."""
    s = _sesion(ctx)
    return await _correr(operaciones.listas, s, fecha, interna)


@mcp.tool()
async def historial_modelo(modelo: str, ctx: Context, dias: int = 14) -> list[dict]:
    """Costo y stock de un modelo por día y proveedor, para ver tendencias ('¿cómo viene el stock del 16 Pro?')."""
    s = _sesion(ctx)
    return await _correr(operaciones.historial, s, modelo, dias)
