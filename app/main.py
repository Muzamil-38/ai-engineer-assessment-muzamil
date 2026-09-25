from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.chatbot import answer_question
from app.clients import UpstreamError
from app.config import Settings
from app.dataset import load_sections
from app.schemas import AskRequest, AskResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    async with httpx.AsyncClient(
        follow_redirects=True,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    ) as http:
        app.state.http = http
        app.state.settings = settings
        app.state.sections = load_sections()
        yield


app = FastAPI(title="CR7 & Heroes", lifespan=lifespan)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.exception_handler(UpstreamError)
async def upstream_error(request: Request, exc: UpstreamError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc), "sources": []})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    errors = [{"loc": error["loc"], "msg": error["msg"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors, "sources": []})


@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, request: Request) -> AskResponse:
    state = request.app.state
    return await answer_question(body.question, state.http, state.settings, state.sections)
