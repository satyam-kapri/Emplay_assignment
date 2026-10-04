import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import Field
from rfp_intelligence.config import Config
from rfp_intelligence.schemas import StrictModel, SearchRequest
from rfp_intelligence.search.service import SearchService
from rfp_intelligence.agents.workflow import Workflow
from rfp_intelligence.providers.llm import ProviderError


class FolderRequest(StrictModel):
    folder: str


class AskRequest(StrictModel):
    question: str = Field(min_length=1)
    bid_ids: list[str] = Field(default_factory=list)


def create_app(config=None):
    config = config or Config.load()

    @asynccontextmanager
    async def lifespan(app):
        app.state.search = SearchService(config)
        yield
        app.state.search.close()

    app = FastAPI(title="RFP Intelligence", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/index")
    async def index(request: FolderRequest):
        try:
            return await asyncio.to_thread(app.state.search.index, request.folder)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/search")
    async def search(q: str = Query(min_length=1), bid_id: list[str] = Query(default=[]),
                     doc_type: list[str] = Query(default=[]), addendum_number: list[int] = Query(default=[]),
                     top_k: int = Query(default=5, ge=1, le=50), mode: str | None = None):
        try:
            request = SearchRequest(query=q, bid_ids=bid_id, doc_types=doc_type,
                                    addendum_numbers=addendum_number, top_k=top_k, mode=mode or config.search_mode)
            return [e.model_dump() for e in await asyncio.to_thread(app.state.search.search, request)]
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/extract")
    async def extract(request: FolderRequest):
        try:
            return await Workflow(app.state.search).extract(request.folder)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except ProviderError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/ask")
    async def ask(request: AskRequest):
        try:
            return await Workflow(app.state.search).ask(request.question, request.bid_ids)
        except ProviderError as exc:
            raise HTTPException(503, str(exc)) from exc

    return app
