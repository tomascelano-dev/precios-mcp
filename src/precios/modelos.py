from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

CONDICIONES = ("nuevo", "cpo", "tester", "usado")


@dataclass
class Oferta:
    """Una fila de la lista de un proveedor, ya estructurada (la estructura la arma Claude al parsear)."""

    proveedor: str
    categoria: str
    condicion: str
    modelo: str
    costo: float | None
    fecha_lista: date
    capacidad: str = ""
    ram_rom: str = ""
    color: str = ""
    bateria: int | None = None
    sufijos: list[str] = field(default_factory=list)
    stock: int | None = None
    precios_volumen: dict[int, float] = field(default_factory=dict)

    def describir(self) -> str:
        return " ".join(p for p in (self.modelo, self.ram_rom or self.capacidad, self.color) if p)


@dataclass
class ItemPrecio:
    oferta: Oferta
    precio: int
    bat_nueva: bool = False


@dataclass
class Alerta:
    tipo: str
    detalle: str
