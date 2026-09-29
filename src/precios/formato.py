from .modelos import Alerta, ItemPrecio, Oferta


def garantia_de(o: Oferta, cfg: dict) -> str | None:
    garantias = cfg["proveedores"][o.proveedor].get("garantia", {})
    return garantias.get(o.condicion, garantias.get("default"))


def entra_en_lista(o: Oferta, lista: dict) -> bool:
    return (
        o.categoria in lista["categorias"]
        and ("condiciones" not in lista or o.condicion in lista["condiciones"])
        and o.modelo.startswith(lista.get("modelo_prefijo", ""))
    )


def armar_lista(lista: dict, items: list[ItemPrecio], cfg: dict, interna: bool = False) -> tuple[str, list[Alerta]]:
    """Texto de WhatsApp de una lista. `interna=True` agrega de qué proveedor sale cada línea."""
    alertas = []

    # La garantía del encabezado sale de los proveedores reales de la lista, no de la categoría:
    # si se mezclan garantías o alguna no está definida, el encabezado no promete ninguna.
    garantias = {garantia_de(it.oferta, cfg) for it in items}
    definidas = sorted(g for g in garantias if g)
    if None in garantias:
        alertas.append(Alerta("garantia_sin_definir", f"{lista['titulo']}: hay productos de un proveedor sin garantía definida"))
    if None not in garantias and len(definidas) == 1:
        linea_garantia = f"✅ Garantía {definidas[0]}"
    else:
        linea_garantia = "✅ Garantía según producto — consultar"
        if len(definidas) > 1:
            alertas.append(Alerta("garantia_mixta", f"{lista['titulo']}: mezcla {', '.join(definidas)}"))

    plantilla = cfg["plantillas"][lista["plantilla"]]
    bloques: dict[str, dict[tuple, list[str]]] = {}
    for it in sorted(items, key=lambda i: (i.oferta.modelo, i.precio)):
        o = it.oferta
        bateria = "Bat. nueva" if it.bat_nueva else (f"{o.bateria}%" if o.bateria is not None else "")
        clave = (o.capacidad, o.ram_rom, it.precio, bateria, tuple(o.sufijos), o.proveedor if interna else "")
        bloques.setdefault(o.modelo, {}).setdefault(clave, []).append(o.color)

    partes = [f"*{lista['emoji']} {lista['titulo']} {lista['emoji']}*\n{linea_garantia}"]
    for modelo, lineas in bloques.items():
        # Las plantillas sin {modelo} (usados) necesitan el modelo como título del bloque.
        texto = [] if "{modelo}" in plantilla else [f"*{modelo}*"]
        for (capacidad, ram_rom, precio, bateria, sufijos, proveedor), colores in lineas.items():
            linea = plantilla.format(
                modelo=modelo,
                capacidad=capacidad,
                ram_rom=ram_rom,
                colores=" / ".join(dict.fromkeys(c for c in colores if c)),
                bateria=bateria,
                moneda=cfg["moneda"],
                precio=precio,
                sufijos="".join(f" {s}" for s in sufijos),
            )
            texto.append(f"{linea}  [{proveedor}]" if interna else linea)
        partes.append("\n".join(texto))
    return "\n\n".join(partes), alertas
