from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import router
from .mcp_server import crear_app, mcp

# streamable_http_app() crea el session manager, así que tiene que ir antes del lifespan.
mcp_app = crear_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="precios", lifespan=lifespan)
app.include_router(router)
app.mount("/mcp", mcp_app)  # los clientes MCP apuntan a /mcp/ (con barra final)


@app.exception_handler(PermissionError)
async def prohibido(_: Request, exc: PermissionError):
    return JSONResponse({"detail": str(exc)}, status_code=403)


@app.exception_handler(ValueError)
async def invalido(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)
