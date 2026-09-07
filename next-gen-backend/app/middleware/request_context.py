# app/middleware/request_context.py

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("nexgen.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0

            logger.exception(
                f"{request.method} {request.url.path} failed after {duration_ms:.2f}ms "
                f"request_id={request_id} error={e}"
            )

            raise

        duration_ms = (time.perf_counter() - start) * 1000.0

        logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} "
            f"duration_ms={duration_ms:.2f} "
            f"request_id={request_id}"
        )

        response.headers["X-Request-ID"] = request_id

        return response