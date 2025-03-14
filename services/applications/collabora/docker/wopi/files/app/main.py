import logging
import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.staticfiles import StaticFiles

from app.model.websockets import ConnectionManager
from app.dependencies import (
    get_connection_manager,
    get_wopi,
)
from app.config import get_settings
from app.routers.wopi import router as wopi
from app.routers.wopi_control import router as wopi_control
from app.routers.documents import router as document


log = logging.getLogger("uvicorn.error")
if get_settings().dev_mode:
    log.warning("DEV mode active, disable for production!")
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)


app = FastAPI()

if get_settings().dev_mode:
    from fastapi.middleware.cors import CORSMiddleware

    origins = [
        "*",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
async def startup():
    log.info("Initalization started")
    wopi_srv = get_wopi()
    wopi_srv.fetch_apps()
    con_mgr = get_connection_manager()
    await con_mgr.announce_documents()
    log.info("Initalization complete")


@app.on_event("startup")
async def register_jobs():
    wopi_srv = get_wopi()

    async def wopi_discovery_task() -> None:
        while True:
            log.info("Autmatic WOPI Discovery update")
            wopi_srv.fetch_apps()
            await asyncio.sleep(60)  # Refresh every 1 Minute

    asyncio.ensure_future(wopi_discovery_task())


app.include_router(wopi, prefix="/wopi")
app.include_router(wopi_control, prefix="/wopi-discovery")
app.include_router(document, prefix="/documents")


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    con_mgr: ConnectionManager = Depends(get_connection_manager),
):
    await con_mgr.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
    except WebSocketDisconnect:
        con_mgr.disconnect(websocket)


app.mount("/", StaticFiles(directory="ui/dist", html=True), name="static")
