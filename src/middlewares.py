import time
from http import HTTPStatus
from json import JSONDecodeError
from uuid import uuid4

from fastapi import Request
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from src.models import LinkRequest
from src.utils import logger


class LogRequest(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        """Log requests."""
        if request.url.path != "/v1" or request.method != "POST":
            return await call_next(request)

        start_time = time.perf_counter()
        try:
            request_body = LinkRequest.model_validate(await request.json())
        except ValidationError, JSONDecodeError, UnicodeDecodeError:
            return JSONResponse(
                status_code=422, content={"detail": "Invalid Byparr request"}
            )
        request.state.byparr_scripted = request_body.has_scripts
        request.state.byparr_request_id = str(request_body.request_id or uuid4())
        logger.info(
            f"From: {request.client.host if request.client else 'unknown'} at {time.strftime('%Y-%m-%d %H:%M:%S')}: {request_body.url}"
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.byparr_request_id
        process_time = time.perf_counter() - start_time

        if response.status_code == HTTPStatus.OK:
            logger.info(f"Done {request_body.url} in {process_time:.2f}s")
        else:
            logger.warning(f"Failed {request_body.url} in {process_time:.2f}s")

        return response
