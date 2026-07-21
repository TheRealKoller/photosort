from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from photosort.config import settings

# Ausschliesslich fuer POST /auth/login genutzt (siehe api/auth.py) - kein API-weites Limit.
# Storage-Backend: Redis ueber settings.redis_url in Produktion (konsistent ueber mehrere
# Backend-Prozesse hinweg), ueberschreibbar auf z.B. "memory://" fuer die Testsuite (siehe
# Settings.resolved_rate_limit_storage_uri und architecture/0002-testkonzept.md).
limiter = Limiter(
    key_func=get_remote_address, storage_uri=settings.resolved_rate_limit_storage_uri()
)
