-- Esquema multi-tenant. Todo cuelga de tenants: un negocio nunca ve filas de otro.
-- En el VPS: docker exec -it stack-postgres psql -U "$POSTGRES_USER" -c "CREATE DATABASE precios;"
--            docker exec -i stack-postgres psql -U "$POSTGRES_USER" -d precios < sql/001_init.sql

CREATE TABLE tenants (
    id      serial PRIMARY KEY,
    slug    text UNIQUE NOT NULL,          -- coincide con config/tenants/<slug>.json
    nombre  text NOT NULL,
    creado  timestamptz NOT NULL DEFAULT now()
);

-- Tokens para REST y MCP. Se guarda solo el sha256; el token en claro se entrega una vez.
CREATE TABLE api_tokens (
    token_sha256 text PRIMARY KEY,
    tenant_id    int NOT NULL REFERENCES tenants ON DELETE CASCADE,
    rol          text NOT NULL CHECK (rol IN ('duenio', 'empleado')),
    descripcion  text,
    creado       timestamptz NOT NULL DEFAULT now()
);

-- Un solo bot de Telegram para todos los negocios: el chat decide el tenant.
CREATE TABLE telegram_chats (
    chat_id    bigint PRIMARY KEY,
    tenant_id  int NOT NULL REFERENCES tenants ON DELETE CASCADE,
    rol        text NOT NULL CHECK (rol IN ('duenio', 'empleado'))
);

-- Una lista por proveedor y día. Guardar todas las listas es lo que da el historial
-- (stock en caída, variaciones de costo) sin trabajo extra.
CREATE TABLE listas_proveedor (
    id              bigserial PRIMARY KEY,
    tenant_id       int NOT NULL REFERENCES tenants ON DELETE CASCADE,
    proveedor       text NOT NULL,
    fecha           date NOT NULL,
    texto_original  text,
    cargada         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, proveedor, fecha)
);

CREATE TABLE ofertas (
    id               bigserial PRIMARY KEY,
    lista_id         bigint NOT NULL REFERENCES listas_proveedor ON DELETE CASCADE,
    categoria        text NOT NULL,
    condicion        text NOT NULL CHECK (condicion IN ('nuevo', 'cpo', 'tester', 'usado')),
    modelo           text NOT NULL,
    capacidad        text NOT NULL DEFAULT '',
    ram_rom          text NOT NULL DEFAULT '',
    color            text NOT NULL DEFAULT '',
    bateria          int,
    sufijos          text[] NOT NULL DEFAULT '{}',
    costo            numeric(10, 2),
    stock            int,
    precios_volumen  jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX ofertas_lista ON ofertas (lista_id);
CREATE INDEX ofertas_modelo ON ofertas (modelo);

-- Alta del primer tenant:
-- INSERT INTO tenants (slug, nombre) VALUES ('demo', 'Tienda Demo');
