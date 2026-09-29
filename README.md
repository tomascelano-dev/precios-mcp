# precios-mcp

[![tests](https://github.com/tomascelano-dev/precios-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/tomascelano-dev/precios-mcp/actions/workflows/tests.yml)

Turns messy wholesale price lists from suppliers into ready-to-send WhatsApp price lists, with each
store's markup applied. Multi-tenant, with two doors onto the same core: a **REST API** (for n8n and
scheduled jobs) and an **MCP server** (so Claude can use it as a set of tools).

Built for a phone retailer that gets daily supplier lists as WhatsApp messages, PDFs or photos.
The repo ships with a fictional store (`config/tenants/demo.json`); real store configs are not versioned.

> Code identifiers and user-facing text are in Spanish, the language of the business it serves.

## The idea: the model reads, the code does the money

| Step | Who does it |
|---|---|
| Read the supplier list as it arrives (free text, abbreviations, one price for several colours) and structure it | **Claude**, through the `cargar_lista_proveedor` tool |
| Typos, colour abbreviations, list expiry, best cost across suppliers, markup, battery surcharge, tester-vs-used dominance, volume-price sanity checks, WhatsApp formatting | **The core** (`src/precios/`), deterministic and unit-tested |
| Each store's rules (markups, suppliers, warranties, templates) | `config/tenants/<slug>.json` |

An LLM is good at reading "IPHONE 16 128 Black/Mid 800" and bad at being trusted with prices. So the
tool contract tells Claude explicitly **not** to fix typos or apply markup: it only structures. Every
number a customer sees comes from code with tests.

```mermaid
flowchart LR
    S["Supplier list<br/>(WhatsApp text, PDF, photo)"] --> C["Claude<br/>structures it"]
    C -- "MCP · cargar_lista_proveedor" --> O
    N["n8n · cron / Telegram"] -- "REST" --> O
    subgraph API["FastAPI · one process"]
        O["operaciones.py<br/>shared by both doors"] --> K["Core: normalise → validate →<br/>best cost → markup → format"]
    end
    O <--> DB[("PostgreSQL<br/>one list per supplier per day")]
    K --> W["WhatsApp price lists<br/>+ alerts for the owner"]
```

## What the core catches

Real cases from supplier lists, each covered by a test in `tests/test_servicio.py`:

- **Volume price typo**: "x3 = 665" when the unit price is 575. Buying more can never cost more per unit, so it raises `precio_volumen`.
- **Colour abbreviations without breaking models**: "Ultra" becomes Ultramarine in a colour, but "S25 Ultra" stays intact.
- **Used vs tester**: a used phone is dropped if a tester of the same model (100% battery, grade A) costs the same or less.
- **Low battery**: used phones under the store's threshold are listed as "new battery" with the surcharge added.
- **Warranty honesty**: the list header only promises a warranty if every product in it comes from a supplier that declares the same one.
- **Stale or missing data**: expired lists, products without a price, inactive suppliers and categories without a markup rule are left out, with an alert.
- **Cost jumps**: day-over-day cost changes above the store's threshold raise `variacion`.

## Demo

`scripts/demo_mcp.py` connects over MCP the way Claude would and loads a deliberately messy list.
Actual output against Postgres 16:

```text
tools: reglas_del_negocio, cargar_lista_proveedor, generar_listas, historial_modelo
negocio: Tienda Demo · categorías: accesorios_apple, airpods, apple_watch, consolas, ipad, iphone, macbook, motorola, samsung, xiaomi

cargada la lista 1 con 6 ofertas

*📱 IPHONE NUEVO 📱*
✅ Garantía según producto — consultar

- *iPhone 16* 128GB — Black / Midnight / Lavender — *U$S 890*

- *iPhone 16 Pro* 256GB — Desert — *U$S 1100*

*📱 IPHONE USADO 📱*
✅ Garantía según producto — consultar

*iPhone 13*
- 128GB | Midnight | Bat. nueva | *U$S 430*

*📱 SAMSUNG 📱*
✅ Garantía según producto — consultar

- Galaxy S25 FE – 8/256 — Ultramarine — *U$S 625*

alertas:
  [precio_volumen] Galaxy S25 FE 8/256 Ultramarine (mayorista): x3 = 665 es más caro que 575; ¿error de tipeo?
  [garantia_sin_definir] IPHONE NUEVO: hay productos de un proveedor sin garantía definida
  ...
```

The input had "Mid", "Lavander" and "Ultra" as colours, three iPhone 16 rows with the same price,
and a used iPhone at 76% battery. The core merged the colours into one line, fixed the names, added
the battery surcharge and flagged the volume price.

## Interfaces

**MCP tools** (`src/precios/mcp_server.py`, MCP Python SDK 2.x, streamable HTTP, stateless):

| Tool | Does |
|---|---|
| `reglas_del_negocio` | Valid categories, conditions, suppliers and lists for the store. Claude calls it first. |
| `cargar_lista_proveedor` | Saves a structured supplier list. Reloading the same supplier and day replaces it. |
| `generar_listas` | WhatsApp lists with markup plus the day's alerts. `interna=True` adds the source supplier (owner only). |
| `historial_modelo` | Cost and stock of a model per day and supplier. |

**REST** (`src/precios/api.py`): `GET /listas`, `POST /listas-proveedor`, `GET /historial?modelo=`, `GET /reglas`, `GET /salud`.

**Auth** (`src/precios/auth.py`), three paths resolved per request:

1. Store API token (`Authorization: Bearer ...`). Only the SHA-256 is stored; the plain token is shown once.
2. n8n via Telegram: a service token plus `X-Chat-Id`; the chat decides the store and the role.
3. Development: `DEV_TOKENS="token:tenant:role"` with no database.

Roles: `duenio` (owner) and `empleado` (employee). Employees never see which supplier a price comes from.

## Tests

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # bin/python on Linux/macOS
.venv/Scripts/python -m pytest                       # 16 unit tests, no database needed
```

The repository layer has its own integration tests against a real Postgres (round-trip types,
list replacement, latest list per supplier, tenant isolation, token and chat sessions, history
window, end-to-end load-and-generate). They are skipped unless `TEST_DATABASE_URL` is set:

```bash
docker run --rm -d --name precios-test -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16
TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/postgres .venv/Scripts/python -m pytest
# 23 passed
```

## Run locally

```bash
# schema + demo store in the test database from above
docker exec -i precios-test psql -U postgres < sql/001_init.sql
docker exec precios-test psql -U postgres -c "INSERT INTO tenants (slug, nombre) VALUES ('demo', 'Tienda Demo');"

DEV_TOKENS="demo:demo:duenio" DATABASE_URL=postgresql://postgres:test@localhost:55432/postgres \
  .venv/Scripts/python -m uvicorn precios.main:app --port 8765

PRECIOS_MCP_URL=http://localhost:8765/mcp/ .venv/Scripts/python scripts/demo_mcp.py
```

MCP endpoint: `http://localhost:8765/mcp/` (trailing slash) with `Authorization: Bearer <token>`.
Without `DATABASE_URL` only `/salud` and `/reglas` work.

## Deploy

It runs as one more container in a Docker Compose stack on a VPS, next to Postgres and n8n
(`docker-compose.snippet.yml`), published only on `127.0.0.1` and reached by n8n over the internal network.

1. Create the database and schema (`sql/001_init.sql`), insert the tenant, copy its config to `config/tenants/<slug>.json`.
2. Create `.env` from `.env.example` and `docker compose up -d --build precios-api`.
3. Tokens: `python scripts/nuevo_token.py <slug> duenio "Claude Desktop"` prints the token once and the SQL to register its hash.
4. To expose the MCP endpoint publicly (for Claude Desktop), add the domain to `MCP_ALLOWED_HOSTS` and route it through the reverse proxy.

**n8n flows**: *in*, a Telegram trigger feeds an AI Agent (Claude) with an MCP Client tool pointing at
`http://precios-api:8000/mcp/`; *out*, a schedule calls `GET /listas` and sends one Telegram message per
list, with the alerts going to the owner. The outbound path uses no AI at all.

## Notes on the MCP Python SDK 2.x

Three things that cost time and are not obvious from the docs:

- `FastMCP` is now `MCPServer` (`mcp.server.mcpserver`), and `stateless_http`, `json_response` and
  `streamable_http_path` go to `streamable_http_app()`, not the constructor. Client result fields are
  snake_case (`is_error`, `structured_content`).
- DNS-rebinding protection only accepts `Host: localhost` by default, so n8n (`precios-api:8000`) and
  any public domain get a **421**. Pass `TransportSecuritySettings(allowed_hosts=...)`, read here from
  `MCP_ALLOWED_HOSTS`.
- Only a `ToolError` message reaches the model. Any other exception shows up as a generic
  "Error executing tool", so domain errors are converted to `ToolError` in `_correr()`.

## Status

Core, REST and MCP are tested locally against Postgres 16. Next: the n8n/Telegram workflows and the
VPS deploy. Store configs live in files; they move to the database when there is a second store.

## Layout

```
src/precios/
  modelos.py      Oferta, ItemPrecio, Alerta
  normalizar.py   typos (model + colour) and colour abbreviations (colour only)
  precios.py      fixed, % or cost-band markup; battery surcharge
  seleccion.py    expiry, missing price, best cost, volume-price check, tester vs used, cost changes
  formato.py      WhatsApp templates; the header warranty comes from the actual suppliers
  servicio.py     the whole pipeline with no DB or HTTP (what the unit tests cover)
  repo.py         Postgres (one list per supplier per day = free history)
  auth.py         store token | service token + X-Chat-Id | DEV_TOKENS
  operaciones.py  what both doors expose
  api.py          REST
  mcp_server.py   MCP
  main.py         FastAPI with the MCP app mounted at /mcp/
scripts/
  demo_mcp.py     MCP client walkthrough against the demo store
  nuevo_token.py  generates a store token and the SQL to register its hash
```
