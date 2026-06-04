from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.infrastructure.coverage.store import CoverageStore

router = APIRouter(tags=["coverage"])

_store: CoverageStore | None = None


def init_coverage(storage_dir: str) -> None:
    global _store
    path = os.path.join(storage_dir, "coverage.json")
    _store = CoverageStore(path)


def get_store() -> CoverageStore:
    if _store is None:
        raise RuntimeError("coverage not initialized")
    return _store


class MarkRequest(BaseModel):
    endpoint: str
    param: str
    vuln_class: str
    status: str = "tried"
    notes: str | None = None


class MarkResponse(BaseModel):
    ok: bool = True
    entry: dict


class UntestedRequest(BaseModel):
    candidates: list[dict]
    vuln_classes: list[str]


@router.post("/coverage/mark")
async def mark_coverage(req: MarkRequest):
    store = get_store()
    entry = store.mark(req.endpoint, req.param, req.vuln_class, req.status, req.notes)
    return MarkResponse(entry=entry.model_dump())


@router.get("/coverage/list")
async def list_coverage(
    endpoint: str | None = None,
    param: str | None = None,
    vuln_class: str | None = None,
    status: str | None = None,
):
    store = get_store()
    return [
        e.model_dump()
        for e in store.list(
            endpoint=endpoint,
            param=param,
            vuln_class=vuln_class,
            status=status,
        )
    ]


@router.post("/coverage/untested")
async def untested_coverage(req: UntestedRequest):
    store = get_store()
    return store.untested(req.candidates, req.vuln_classes)


@router.get("/coverage/summary")
async def coverage_summary():
    store = get_store()
    return store.summary().model_dump()


@router.post("/coverage/clear")
async def clear_coverage():
    store = get_store()
    store.clear()
    return {"ok": True}
