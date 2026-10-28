"""API + web. Los jobs corren en 2 workers (límite de concurrencia hacia ElevenLabs)."""
import asyncio
import hmac
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response

from .core import BudgetExceeded, Forge, Req
from .eleven import Eleven, ElevenError

WORKERS, MAX_JOBS = 2, 200
STATIC = Path(__file__).parent / "static"


def create_app(forge: Forge):
    jobs: dict[str, dict] = {}      # ponytail: en memoria, se pierden al reiniciar; SQLite si hiciera falta persistirlos
    queue: asyncio.Queue = asyncio.Queue()

    async def worker():
        while True:
            jid, req = await queue.get()
            jobs[jid]["status"] = "running"
            try:
                jobs[jid].update(status="done", results=await asyncio.to_thread(forge.generate, req))
            except (BudgetExceeded, ElevenError) as e:
                jobs[jid].update(status="error", error=str(e))
            except Exception as e:      # un fallo inesperado no debe matar al worker
                jobs[jid].update(status="error", error=f"{type(e).__name__}: {e}")

    @asynccontextmanager
    async def lifespan(_):
        tasks = [asyncio.create_task(worker()) for _ in range(WORKERS)]
        yield
        for t in tasks:
            t.cancel()

    def auth(x_api_key: str | None = Header(None)):
        want = os.environ.get("SF_API_KEY")      # sin SF_API_KEY la API queda abierta (solo escucha en 127.0.0.1)
        if want and not hmac.compare_digest(x_api_key or "", want):
            raise HTTPException(401, "API key inválida")

    app = FastAPI(title="sample-forge", lifespan=lifespan)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/budget", dependencies=[Depends(auth)])
    def budget():
        return forge.status()

    @app.post("/api/estimate", dependencies=[Depends(auth)])
    def estimate(req: Req):
        return forge.estimate(req)

    @app.post("/api/jobs", status_code=202, dependencies=[Depends(auth)])
    async def create_job(req: Req):
        est = forge.estimate(req)
        if est["credits"] > est["left"]:
            raise HTTPException(402, f"Presupuesto insuficiente: ~{est['credits']} créditos, quedan {est['left']}")
        jid = uuid.uuid4().hex[:10]
        jobs[jid] = dict(id=jid, status="queued", estimate=est)
        while len(jobs) > MAX_JOBS:
            jobs.pop(next(iter(jobs)))
        await queue.put((jid, req))
        return jobs[jid]

    @app.get("/api/jobs/{jid}", dependencies=[Depends(auth)])
    def job(jid: str):
        if jid not in jobs:
            raise HTTPException(404, "job desconocido")
        return jobs[jid]

    @app.get("/api/samples", dependencies=[Depends(auth)])
    def samples(q: str = "", kind: str | None = Query(None, pattern="^(sfx|vox)$"), note: str | None = Query(
            None, pattern="^[A-G]#?-?[0-9]?$"), max_dur: float | None = Query(None, gt=0), limit: int = Query(100, le=500)):
        return forge.db.search(q, kind, note, max_dur, limit)

    @app.get("/api/samples/{sid}/audio", dependencies=[Depends(auth)])
    def audio(sid: str):
        s = forge.db.get(sid) if re.fullmatch(r"[0-9a-f]{12}", sid) else None
        if not s:
            raise HTTPException(404, "sample desconocido")
        return FileResponse(forge.dir / s["file"], media_type="audio/wav")

    @app.get("/api/export.zip", dependencies=[Depends(auth)])
    def export(ids: str = Query(..., max_length=2000)):
        found = [i for i in ids.split(",") if re.fullmatch(r"[0-9a-f]{12}", i)]
        if not found:
            raise HTTPException(400, "sin ids válidos")
        return Response(forge.zip(found), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="sample-forge.zip"'})

    return app


app = create_app(Forge(Eleven()))
