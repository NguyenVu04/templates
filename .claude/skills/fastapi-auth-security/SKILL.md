---
name: fastapi-auth-security
description: Guidance for authentication and security hardening in FastAPI services — JWT/OAuth2 login flows, password hashing, role-based access control, and a security review checklist covering CORS, rate limiting, secrets, SQL injection, and upload handling. Use this skill whenever the user wants to add login/JWT/OAuth2, implement permissions or role checks, configure CORS, add rate limiting, or asks for a security review of an API.
---

# FastAPI Auth & Security

Guidance for building authentication and running a security pass on a FastAPI service.

## Non-negotiable defaults

1. **Type hints everywhere** — FastAPI's DI (including auth dependencies) depends on them.
2. **Settings via `pydantic-settings`** — `secret_key` and other sensitive config come from one `Settings` class loaded from env, never `os.getenv` scattered around or hardcoded values.
3. **Secrets never appear in code, logs, or committed files** — `.env` is gitignored; only `.env.example` with dummy values is committed.

## JWT auth — the standard recipe

```bash
uv add pyjwt "passlib[bcrypt]"
```

`services/auth_service.py` (core pieces):

```python
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from myproject.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str: return pwd_context.hash(p)
def verify_password(plain: str, hashed: str) -> bool: return pwd_context.verify(plain, hashed)

def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expire}, settings.secret_key, algorithm="HS256")
```

`api/deps.py` — the auth dependency chain:

```python
from typing import Annotated
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    cred_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials",
                             headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        sub = payload.get("sub")
    except jwt.PyJWTError:
        raise cred_exc
    user = await UserRepository(db).get(int(sub)) if sub else None
    if user is None:
        raise cred_exc
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]
```

Protect an endpoint by simply adding `user: CurrentUser` to its signature. For role checks, use a dependency factory:

```python
def require_role(role: str):
    async def checker(user: CurrentUser) -> User:
        if role not in user.roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user
    return checker

AdminUser = Annotated[User, Depends(require_role("admin"))]
```

Rules:
- 401 = who are you (bad/missing token); 403 = I know you, you can't do this. Don't mix them up.
- Login errors are generic ("Incorrect email or password") — never reveal which field was wrong.
- Refresh tokens: store server-side (or store a revocable ID), rotate on use. Access tokens stay short-lived (15–30 min) and stateless.
- **Authorization ≠ authentication**: every endpoint that fetches a resource by ID must check the current user may access THAT resource (IDOR). This check lives in the service layer, not the router.

## Security hardening checklist

Run through this before any deploy, and when asked to "review security":

1. **CORS** — explicit origins list from Settings; never `allow_origins=["*"]` together with `allow_credentials=True`.
2. **Secrets** — only from env/secret manager. Grep the repo for the secret key before shipping.
3. **SQL injection** — a non-issue if everything goes through SQLAlchemy expressions; audit any `text()` usage for bound parameters.
4. **Rate limiting** — `slowapi` at minimum on `/auth/token` and other write-heavy public endpoints; production usually enforces at the gateway too.
5. **Docs exposure** — decide deliberately: internal APIs often set `docs_url=None` in prod (via Settings flag).
6. **Upload endpoints** — enforce content-type allowlist and size limit; never trust the client filename (generate your own).
7. **Response schemas** — recheck that no Read schema includes `hashed_password`, tokens, or internal flags.
8. **Headers** — behind a proxy, ensure `X-Forwarded-*` handling (`--proxy-headers` in uvicorn) so rate limiting/logging sees real client IPs.
9. **Dependency audit** — `uv run pip-audit` (add as dev dep) or GitHub Dependabot.

Re-run this checklist after any auth-adjacent change, not just before deploys.
