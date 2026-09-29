"""El pipeline completo, sin base de datos ni HTTP: ofertas crudas + config → listas de WhatsApp + alertas."""

from dataclasses import asdict
from datetime import date

from .formato import armar_lista, entra_en_lista
from .modelos import Alerta, Oferta
from .normalizar import normalizar
from .precios import SinRegla, precio_venta
from .seleccion import (
    agrupar_por_categoria_sin_regla,
    dominancia_tester,
    mejor_costo,
    validar_volumen,
    variaciones,
    vigentes,
)


def _preparar(ofertas: list[Oferta], cfg: dict, hoy: date) -> tuple[list[Oferta], list[Alerta]]:
    normalizadas = [normalizar(o, cfg) for o in ofertas]
    validas, alertas = vigentes(normalizadas, hoy, cfg)
    for o in validas:
        alertas += validar_volumen(o)
    return mejor_costo(validas), alertas


def generar(
    ofertas: list[Oferta],
    cfg: dict,
    hoy: date,
    ofertas_ayer: list[Oferta] | None = None,
    interna: bool = False,
) -> dict:
    elegidas, alertas = _preparar(ofertas, cfg, hoy)

    if ofertas_ayer:
        # Las de ayer se evalúan como si fuera ayer, para que no las descarte la vigencia.
        previas, _ = _preparar(ofertas_ayer, cfg, max(o.fecha_lista for o in ofertas_ayer))
        alertas += variaciones(elegidas, previas, cfg["alerta_variacion_pct"])

    items, sin_regla = [], []
    for o in elegidas:
        try:
            item, a = precio_venta(o, cfg)
        except SinRegla:
            sin_regla.append(o.categoria)
            continue
        items.append(item)
        alertas += a
    alertas += agrupar_por_categoria_sin_regla(sin_regla)

    items, a = dominancia_tester(items)
    alertas += a

    listas, asignados = {}, set()
    for lista in cfg["listas"]:
        # Cada producto entra en la primera lista que lo acepta (IPHONE 18 va antes que IPHONE NUEVO).
        propios = [it for it in items if id(it) not in asignados and entra_en_lista(it.oferta, lista)]
        if not propios:
            continue
        asignados.update(id(it) for it in propios)
        listas[lista["titulo"]], a = armar_lista(lista, propios, cfg, interna)
        alertas += a

    huerfanos = sorted({it.oferta.categoria for it in items if id(it) not in asignados})
    for categoria in huerfanos:
        alertas.append(Alerta("sin_lista", f"{categoria}: tiene precio pero ninguna lista la incluye"))

    return {"listas": listas, "alertas": [asdict(a) for a in alertas]}
