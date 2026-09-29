from collections import defaultdict
from datetime import date

from .modelos import Alerta, ItemPrecio, Oferta


def _clave(o: Oferta) -> tuple:
    # Sin proveedor: dos proveedores con el mismo producto compiten por la misma clave.
    return (o.categoria, o.condicion, o.modelo, o.capacidad, o.ram_rom, o.color, o.bateria, tuple(o.sufijos))


def vigentes(ofertas: list[Oferta], hoy: date, cfg: dict) -> tuple[list[Oferta], list[Alerta]]:
    """Descarta proveedores inactivos o desconocidos, listas vencidas y productos sin precio."""
    quedan, alertas = [], []
    vencidos: set[tuple[str, date]] = set()
    desconocidos: set[str] = set()
    sin_precio = 0
    for o in ofertas:
        prov = cfg["proveedores"].get(o.proveedor)
        if prov is None:
            desconocidos.add(o.proveedor)
            continue
        if not prov.get("activo", True):
            continue
        if (hoy - o.fecha_lista).days > prov.get("vigencia_dias", 1):
            vencidos.add((o.proveedor, o.fecha_lista))
            continue
        if o.costo is None:
            sin_precio += 1
            continue
        quedan.append(o)

    for prov, fecha in sorted(vencidos):
        alertas.append(Alerta("lista_vencida", f"{prov}: última lista del {fecha:%d/%m}, descartada"))
    for prov in sorted(desconocidos):
        alertas.append(Alerta("proveedor_desconocido", f"{prov}: no está en la config, se ignora"))
    if sin_precio:
        alertas.append(Alerta("sin_precio", f"{sin_precio} producto(s) sin precio declarado, excluidos"))
    return quedan, alertas


def validar_volumen(o: Oferta) -> list[Alerta]:
    """Comprar más unidades nunca puede salir más caro por unidad. Detecta el caso 'S25 FE 3x665'."""
    alertas, tope = [], o.costo
    for cantidad in sorted(o.precios_volumen):
        precio = o.precios_volumen[cantidad]
        if tope is not None and precio > tope:
            alertas.append(Alerta(
                "precio_volumen",
                f"{o.describir()} ({o.proveedor}): x{cantidad} = {precio:g} es más caro que {tope:g}; ¿error de tipeo?",
            ))
        tope = precio if tope is None else min(tope, precio)
    return alertas


def mejor_costo(ofertas: list[Oferta]) -> list[Oferta]:
    mejores: dict[tuple, Oferta] = {}
    for o in ofertas:
        actual = mejores.get(_clave(o))
        if actual is None or o.costo < actual.costo:
            mejores[_clave(o)] = o
    return list(mejores.values())


def dominancia_tester(items: list[ItemPrecio]) -> tuple[list[ItemPrecio], list[Alerta]]:
    """Un usado sale de la lista si hay un tester del mismo modelo y capacidad al mismo precio o menos
    (el tester viene con batería 100% y grado A)."""
    tester_min: dict[tuple, int] = {}
    for it in items:
        o = it.oferta
        if o.condicion == "tester":
            k = (o.modelo, o.capacidad)
            tester_min[k] = min(tester_min.get(k, it.precio), it.precio)

    quedan, alertas = [], []
    for it in items:
        o = it.oferta
        tope = tester_min.get((o.modelo, o.capacidad))
        if o.condicion == "usado" and tope is not None and tope <= it.precio:
            alertas.append(Alerta("usado_dominado", f"{o.describir()}: usado {it.precio} vs tester {tope}, sacado de usados"))
            continue
        quedan.append(it)
    return quedan, alertas


def variaciones(hoy: list[Oferta], ayer: list[Oferta], umbral_pct: float) -> list[Alerta]:
    anteriores = {_clave(o): o for o in ayer}
    alertas = []
    for o in hoy:
        previa = anteriores.get(_clave(o))
        if previa is None or not previa.costo:
            continue
        cambio = (o.costo - previa.costo) / previa.costo * 100
        if abs(cambio) >= umbral_pct:
            alertas.append(Alerta("variacion", f"{o.describir()}: costo {previa.costo:g} → {o.costo:g} ({cambio:+.0f}%)"))
    return alertas


def agrupar_por_categoria_sin_regla(categorias: list[str]) -> list[Alerta]:
    conteo = defaultdict(int)
    for c in categorias:
        conteo[c] += 1
    return [Alerta("sin_regla", f"{c}: {n} producto(s) sin markup definido, no se publican") for c, n in sorted(conteo.items())]
