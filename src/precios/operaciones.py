"""Las operaciones que exponen tanto la API REST como el servidor MCP. Una sola implementación, dos puertas."""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from . import repo, servicio
from .auth import Sesion
from .config import cargar_config


class OfertaIn(BaseModel):
    categoria: str = Field(description="Una de las categorías de reglas_del_negocio (p. ej. 'iphone', 'samsung').")
    condicion: Literal["nuevo", "cpo", "tester", "usado"]
    modelo: str = Field(description="Modelo sin capacidad ni color, p. ej. 'iPhone 16 Pro' o 'Galaxy S25 FE'.")
    costo: float | None = Field(None, description="Precio unitario del proveedor en USD. null si no declara precio.")
    capacidad: str = Field("", description="Almacenamiento, p. ej. '256GB'.")
    ram_rom: str = Field("", description="Solo Android: '8/256'.")
    color: str = Field("", description="Un solo color por oferta. Tal como lo escribe el proveedor.")
    bateria: int | None = Field(None, description="Solo usados: porcentaje de batería declarado.")
    sufijos: list[str] = Field(default_factory=list, description="Aclaraciones: '(tiene detalles)', '(SIM física)', '| (S/CARG)'.")
    stock: int | None = None
    precios_volumen: dict[int, float] = Field(default_factory=dict, description="Precio unitario por cantidad: {3: 665, 5: 560}.")


class CargaLista(BaseModel):
    proveedor: str
    fecha: date
    ofertas: list[OfertaIn]
    texto_original: str = ""


def reglas(s: Sesion) -> dict:
    cfg = cargar_config(s.tenant)
    return {
        "negocio": cfg["nombre"],
        "categorias": sorted(cfg["markup"]),
        "condiciones": ["nuevo", "cpo", "tester", "usado"],
        "proveedores_activos": sorted(p for p, v in cfg["proveedores"].items() if v.get("activo", True)),
        "listas": [l["titulo"] for l in cfg["listas"]],
    }


def cargar(s: Sesion, carga: CargaLista) -> dict:
    cfg = cargar_config(s.tenant)
    if carga.proveedor not in cfg["proveedores"]:
        raise ValueError(f"Proveedor desconocido: {carga.proveedor}. Válidos: {', '.join(cfg['proveedores'])}")
    lista_id = repo.guardar_lista(
        s.tenant, carga.proveedor, carga.fecha, [o.model_dump() for o in carga.ofertas], carga.texto_original
    )
    return {"lista_id": lista_id, "ofertas_guardadas": len(carga.ofertas)}


def listas(s: Sesion, hoy: date | None = None, interna: bool = False) -> dict:
    # La versión interna dice de qué proveedor sale cada producto: no es para empleados.
    if interna and s.rol != "duenio":
        raise PermissionError("La lista interna (con proveedores) es solo para el dueño")
    hoy = hoy or date.today()
    cfg = cargar_config(s.tenant)
    return servicio.generar(
        repo.ultimas_ofertas(s.tenant, hoy),
        cfg,
        hoy,
        ofertas_ayer=repo.ultimas_ofertas(s.tenant, hoy - timedelta(days=1)),
        interna=interna,
    )


def historial(s: Sesion, modelo: str, dias: int = 14) -> list[dict]:
    return repo.historial(s.tenant, modelo, dias)
