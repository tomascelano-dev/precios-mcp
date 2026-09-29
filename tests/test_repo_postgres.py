"""repo.py contra un Postgres real. Se saltea si no hay TEST_DATABASE_URL.

    docker run --rm -d --name precios-test -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16
    TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/postgres pytest

El fixture borra y recrea el esquema public en cada test: usar una base descartable.
"""

import os
from datetime import date, timedelta
from pathlib import Path

import psycopg
import pytest

from precios import operaciones, repo
from precios.auth import Sesion
from precios.operaciones import CargaLista, OfertaIn

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="sin TEST_DATABASE_URL")

ESQUEMA = (Path(__file__).resolve().parents[1] / "sql" / "001_init.sql").read_text(encoding="utf-8")
HOY = date.today()


@pytest.fixture(autouse=True)
def base(monkeypatch):
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        c.execute(ESQUEMA)
        c.execute("INSERT INTO tenants (slug, nombre) VALUES ('demo', 'Tienda Demo'), ('otra', 'Otra Tienda')")
    monkeypatch.setenv("DATABASE_URL", URL)


def oferta(**kw) -> dict:
    base = dict(categoria="iphone", condicion="nuevo", modelo="iPhone 16", capacidad="128GB", ram_rom="",
                color="Black", bateria=None, sufijos=[], costo=800.0, stock=None, precios_volumen={})
    return {**base, **kw}


def test_ida_y_vuelta_conserva_los_tipos():
    repo.guardar_lista("demo", "mayorista", HOY, [
        oferta(categoria="samsung", modelo="Galaxy S25 FE", capacidad="", ram_rom="8/256", costo=575,
               sufijos=["(SIM física)"], stock=4, precios_volumen={3: 665, 5: 560}),
        oferta(modelo="iPhone 13", condicion="usado", bateria=76, costo=None),
    ], "texto tal como llegó")

    ofertas = {o.modelo: o for o in repo.ultimas_ofertas("demo", HOY)}
    s25 = ofertas["Galaxy S25 FE"]
    assert (s25.proveedor, s25.fecha_lista, s25.ram_rom) == ("mayorista", HOY, "8/256")
    assert s25.costo == 575.0 and isinstance(s25.costo, float)
    assert s25.sufijos == ["(SIM física)"] and s25.stock == 4
    assert s25.precios_volumen == {3: 665, 5: 560}  # las claves vuelven como int, no como str de JSON
    assert ofertas["iPhone 13"].costo is None and ofertas["iPhone 13"].bateria == 76


def test_recargar_el_mismo_proveedor_y_dia_reemplaza_la_lista():
    repo.guardar_lista("demo", "oficial", HOY, [oferta(), oferta(modelo="iPhone 16 Pro")], "")
    repo.guardar_lista("demo", "oficial", HOY, [oferta(costo=790)], "corrección")
    ofertas = repo.ultimas_ofertas("demo", HOY)
    assert [(o.modelo, o.costo) for o in ofertas] == [("iPhone 16", 790.0)]


def test_toma_la_ultima_lista_de_cada_proveedor_hasta_la_fecha():
    ayer = HOY - timedelta(days=1)
    repo.guardar_lista("demo", "oficial", ayer, [oferta(costo=810)], "")
    repo.guardar_lista("demo", "oficial", HOY, [oferta(costo=800)], "")
    repo.guardar_lista("demo", "semi_nuevos", ayer, [oferta(costo=780)], "")

    hoy = sorted((o.proveedor, o.fecha_lista, o.costo) for o in repo.ultimas_ofertas("demo", HOY))
    assert hoy == [("oficial", HOY, 800.0), ("semi_nuevos", ayer, 780.0)]
    assert [o.costo for o in repo.ultimas_ofertas("demo", ayer) if o.proveedor == "oficial"] == [810.0]


def test_un_negocio_no_ve_las_listas_de_otro():
    repo.guardar_lista("otra", "oficial", HOY, [oferta(costo=1)], "")
    assert repo.ultimas_ofertas("demo", HOY) == []
    assert repo.historial("demo", "iPhone", 14) == []


def test_sesiones_por_token_hasheado_y_por_chat():
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute(
            "INSERT INTO api_tokens (token_sha256, tenant_id, rol) SELECT %s, id, 'duenio' FROM tenants WHERE slug = 'demo'",
            (repo.hash_token("secreto"),),
        )
        c.execute("INSERT INTO telegram_chats (chat_id, tenant_id, rol) SELECT -100123, id, 'empleado' FROM tenants WHERE slug = 'otra'")
    assert repo.sesion_por_token("secreto") == ("demo", "duenio")
    assert repo.sesion_por_token("otro") is None
    assert repo.sesion_por_chat(-100123) == ("otra", "empleado")


def test_historial_filtra_por_modelo_y_ventana():
    repo.guardar_lista("demo", "oficial", HOY - timedelta(days=30), [oferta(costo=900)], "")
    repo.guardar_lista("demo", "oficial", HOY, [oferta(), oferta(modelo="Galaxy S25", categoria="samsung")], "")
    filas = repo.historial("demo", "iphone", 14)
    assert [(f["modelo"], f["costo"], f["fecha"]) for f in filas] == [("iPhone 16", 800.0, HOY.isoformat())]


def test_de_punta_a_punta_cargar_y_generar_listas():
    duenio, empleado = Sesion("demo", "duenio"), Sesion("demo", "empleado")
    operaciones.cargar(duenio, CargaLista(proveedor="oficial", fecha=HOY, ofertas=[
        OfertaIn(categoria="iphone", condicion="nuevo", modelo="iPhone 16", capacidad="128GB", color="Mid", costo=800),
    ]))

    publica = operaciones.listas(empleado, HOY)
    assert "- *iPhone 16* 128GB — Midnight — *U$S 890*" in publica["listas"]["IPHONE NUEVO"]
    assert "[oficial]" in operaciones.listas(duenio, HOY, interna=True)["listas"]["IPHONE NUEVO"]
    with pytest.raises(PermissionError):
        operaciones.listas(empleado, HOY, interna=True)
