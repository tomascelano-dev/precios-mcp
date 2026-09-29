import copy
from datetime import date

import pytest

from precios.config import cargar_config
from precios.modelos import Oferta
from precios.precios import SinRegla, markup_para
from precios.servicio import generar

HOY = date(2026, 9, 24)
AYER = date(2026, 9, 23)


@pytest.fixture
def cfg():
    return copy.deepcopy(cargar_config("demo"))


def oferta(**kw) -> Oferta:
    base = dict(proveedor="oficial", categoria="iphone", condicion="nuevo", modelo="iPhone 16", capacidad="128GB",
                color="Black", costo=800.0, fecha_lista=AYER)
    return Oferta(**{**base, **kw})


def tipos(resultado) -> list[str]:
    return [a["tipo"] for a in resultado["alertas"]]


def test_markup_fijo_por_categoria(cfg):
    r = generar([oferta()], cfg, HOY)
    assert "*U$S 890*" in r["listas"]["IPHONE NUEVO"]


def test_markup_por_franjas_y_porcentaje(cfg):
    cfg["markup"]["accesorios_apple"] = [{"hasta": 50, "markup": 25}, {"hasta": 150, "markup": "40%"}, {"markup": 80}]
    assert markup_para("accesorios_apple", 20, cfg) == 25
    assert markup_para("accesorios_apple", 100, cfg) == 40
    assert markup_para("accesorios_apple", 300, cfg) == 80


def test_categoria_sin_regla_no_se_publica(cfg):
    with pytest.raises(SinRegla):
        markup_para("jbl", 100, cfg)
    r = generar([oferta(categoria="jbl", modelo="JBL Flip 6")], cfg, HOY)
    assert r["listas"] == {}
    assert "sin_regla" in tipos(r)


def test_margen_alto_en_accesorio_barato(cfg):
    r = generar([oferta(categoria="accesorios_apple", modelo="Cable USB-C", capacidad="", costo=20)], cfg, HOY)
    assert "margen_alto" in tipos(r)


def test_mejor_costo_entre_proveedores(cfg):
    r = generar([oferta(costo=800), oferta(proveedor="semi_nuevos", costo=780)], cfg, HOY, interna=True)
    lista = r["listas"]["IPHONE NUEVO"]
    assert "*U$S 870*" in lista and "[semi_nuevos]" in lista and "890" not in lista


def test_lista_vencida_y_sin_precio_se_descartan(cfg):
    r = generar([oferta(fecha_lista=date(2026, 9, 17)), oferta(modelo="iPhone 15", costo=None)], cfg, HOY)
    assert r["listas"] == {}
    assert {"lista_vencida", "sin_precio"} <= set(tipos(r))


def test_proveedor_inactivo_se_ignora(cfg):
    r = generar([oferta(proveedor="alternativo", categoria="motorola", modelo="Moto G85")], cfg, HOY)
    assert r["listas"] == {}


def test_bateria_baja_pasa_a_bateria_nueva(cfg):
    r = generar([oferta(proveedor="semi_nuevos", condicion="usado", modelo="iPhone 13", bateria=76, costo=300)], cfg, HOY)
    lista = r["listas"]["IPHONE USADO"]
    assert "| Bat. nueva |" in lista and "*U$S 430*" in lista  # 300 + 90 + 40


def test_error_de_tipeo_en_precio_por_volumen(cfg):
    s25 = oferta(proveedor="mayorista", categoria="samsung", modelo="Galaxy S25 FE", capacidad="", ram_rom="8/256",
                 costo=575, precios_volumen={3: 665, 5: 560})
    r = generar([s25], cfg, HOY)
    assert [a for a in r["alertas"] if a["tipo"] == "precio_volumen" and "x3 = 665" in a["detalle"]]


def test_tester_saca_al_usado_mas_caro(cfg):
    tester = oferta(condicion="tester", modelo="iPhone 15 Pro Max", capacidad="256GB", costo=600)
    usado = oferta(proveedor="semi_nuevos", condicion="usado", modelo="iPhone 15 Pro Max", capacidad="256GB",
                   bateria=84, costo=640)
    r = generar([tester, usado], cfg, HOY)
    assert "IPHONE USADO" not in r["listas"]
    assert "usado_dominado" in tipos(r)


def test_colores_con_mismo_precio_van_en_una_linea(cfg):
    ofertas = [oferta(color="Mid"), oferta(color="Lavander"), oferta(color="White", costo=810)]
    lista = generar(ofertas, cfg, HOY)["listas"]["IPHONE NUEVO"]
    assert "- *iPhone 16* 128GB — Lavender / Midnight — *U$S 890*" in lista or \
           "- *iPhone 16* 128GB — Midnight / Lavender — *U$S 890*" in lista
    assert "White — *U$S 900*" in lista


def test_abreviatura_de_color_no_toca_el_modelo(cfg):
    r = generar([oferta(proveedor="oficial", categoria="samsung", modelo="Galaxy S25 Ultra", capacidad="",
                        ram_rom="12/256", color="Ultra")], cfg, HOY)
    assert "- Galaxy S25 Ultra – 12/256 — Ultramarine" in r["listas"]["SAMSUNG"]


def test_iphone_18_va_a_su_propia_lista(cfg):
    r = generar([oferta(modelo="iPhone 18 Pro"), oferta()], cfg, HOY)
    assert "iPhone 18" in r["listas"]["IPHONE 18"]
    assert "iPhone 18" not in r["listas"]["IPHONE NUEVO"]


def test_garantia_del_encabezado_sale_del_proveedor(cfg):
    solo_oficial = generar([oferta()], cfg, HOY)
    assert "✅ Garantía oficial 12 meses" in solo_oficial["listas"]["IPHONE NUEVO"]

    mezclado = generar([oferta(), oferta(proveedor="mayorista", modelo="iPhone 16 Pro")], cfg, HOY)
    assert "✅ Garantía según producto" in mezclado["listas"]["IPHONE NUEVO"]
    assert "garantia_sin_definir" in tipos(mezclado)


def test_variacion_contra_lista_anterior(cfg):
    ayer = [oferta(fecha_lista=date(2026, 9, 22), costo=800)]
    hoy = [oferta(costo=900)]
    r = generar(hoy, cfg, HOY, ofertas_ayer=ayer)
    assert [a for a in r["alertas"] if a["tipo"] == "variacion" and "+12%" in a["detalle"]]


def test_categoria_con_regla_pero_sin_lista(cfg):
    r = generar([oferta(categoria="accesorios_apple", modelo="Pencil Pro", capacidad="", costo=130)], cfg, HOY)
    assert "sin_lista" in tipos(r)
