import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from scalar_fastapi import get_scalar_api_reference

from app.common.responses import ErrorResponse
from app.database import lifespan
from app.routers import chat_router, documents_router, session_router, user_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

app = FastAPI(
    title="Ai Agent API Reference",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)

app.include_router(user_router)
app.include_router(session_router)
app.include_router(chat_router)
app.include_router(documents_router)

@app.get("/docs", include_in_schema=False)
def scalar_docs() -> HTMLResponse:
    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title="Ai Agent API Reference",
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErrorResponse)
async def error_response_handler(request: Request, exc: ErrorResponse) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "message": exc.message},
    )


@app.get("/", include_in_schema=False)
def read_root() -> dict:
    return {"message": "AI Agent is running."}


@app.get("/health", include_in_schema=False)
def health_check() -> dict:
    return {"status": "healthy"}


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
