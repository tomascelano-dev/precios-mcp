"""Genera un token de API y el SQL para darlo de alta. El token en claro se muestra una sola vez.

    python scripts/nuevo_token.py demo duenio "Claude Desktop"
"""

import hashlib
import secrets
import sys

tenant, rol, descripcion = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""
if rol not in ("duenio", "empleado"):
    sys.exit("rol: duenio | empleado")

token = secrets.token_urlsafe(32)
sha = hashlib.sha256(token.encode()).hexdigest()
descripcion = descripcion.replace("'", "''")
print(f"TOKEN (guardalo ahora, no se vuelve a mostrar):\n  {token}\n")
print("SQL:")
print(f"  INSERT INTO api_tokens (token_sha256, tenant_id, rol, descripcion)")
print(f"  SELECT '{sha}', id, '{rol}', '{descripcion}' FROM tenants WHERE slug = '{tenant}';")
