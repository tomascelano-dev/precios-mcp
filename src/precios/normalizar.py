import re

from .modelos import Oferta

_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]+")


def _reemplazar_palabras(texto: str, diccionario: dict[str, str]) -> str:
    return _PALABRA.sub(lambda m: diccionario.get(m.group(0), m.group(0)), texto).strip()


def normalizar(oferta: Oferta, cfg: dict) -> Oferta:
    typos = cfg.get("typos", {})
    oferta.modelo = _reemplazar_palabras(oferta.modelo, typos)
    oferta.color = _reemplazar_palabras(oferta.color, typos)
    # Las abreviaturas de color van SOLO sobre el color: "Ultra" es Ultramarine en un color,
    # pero en el modelo es "S25 Ultra".
    oferta.color = _reemplazar_palabras(oferta.color, cfg.get("colores_abreviados", {}))
    return oferta
