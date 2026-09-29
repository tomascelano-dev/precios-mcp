import math

from .modelos import Alerta, ItemPrecio, Oferta


class SinRegla(Exception):
    """La categoría no tiene markup definido: el producto no se publica hasta que el dueño la defina."""


def _valor(markup: float | str, costo: float) -> float:
    if isinstance(markup, str) and markup.endswith("%"):
        return costo * float(markup[:-1]) / 100
    return float(markup)


def markup_para(categoria: str, costo: float, cfg: dict) -> float:
    """El markup de una categoría es un monto fijo, un porcentaje ("40%") o una lista de franjas
    por costo: [{"hasta": 50, "markup": 25}, {"markup": 80}]. La primera franja que cubre el costo gana."""
    franjas = cfg["markup"].get(categoria)
    if franjas is None:
        raise SinRegla(categoria)
    if not isinstance(franjas, list):
        franjas = [{"markup": franjas}]
    for franja in franjas:
        if "hasta" not in franja or costo <= franja["hasta"]:
            return _valor(franja["markup"], costo)
    raise SinRegla(f"{categoria} (ninguna franja cubre costo {costo:g})")


def precio_venta(oferta: Oferta, cfg: dict) -> tuple[ItemPrecio, list[Alerta]]:
    alertas = []
    markup = markup_para(oferta.categoria, oferta.costo, cfg)
    precio = oferta.costo + markup

    bat_nueva = False
    bateria = cfg["bateria"]
    if oferta.condicion == "usado" and oferta.bateria is not None and oferta.bateria < bateria["umbral"]:
        precio += bateria["extra"]
        bat_nueva = True

    if markup / oferta.costo * 100 > cfg["alerta_margen_pct"]:
        alertas.append(Alerta(
            "margen_alto",
            f"{oferta.describir()}: costo {oferta.costo:g} → {math.ceil(precio)} (+{markup / oferta.costo:.0%})",
        ))
    return ItemPrecio(oferta, math.ceil(precio), bat_nueva), alertas
