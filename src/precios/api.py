from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request

from . import auth, operaciones
from .auth import Sesion
from .operaciones import CargaLista

router = APIRouter()


def sesion(request: Request) -> Sesion:
    s = auth.resolver(request.headers)
    if s is None:
        raise HTTPException(401, "Token inválido o ausente")
    return s


@router.get("/salud")
def salud() -> dict:
    return {"ok": True}


@router.get("/reglas")
def reglas(s: Sesion = Depends(sesion)) -> dict:
    return operaciones.reglas(s)


@router.post("/listas-proveedor")
def cargar_lista(carga: CargaLista, s: Sesion = Depends(sesion)) -> dict:
    return operaciones.cargar(s, carga)


@router.get("/listas")
def listas(fecha: date | None = None, interna: bool = False, s: Sesion = Depends(sesion)) -> dict:
    return operaciones.listas(s, fecha, interna)


@router.get("/historial")
def historial(modelo: str, dias: int = 14, s: Sesion = Depends(sesion)) -> list[dict]:
    return operaciones.historial(s, modelo, dias)
