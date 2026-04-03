# gateway/router.py
import json

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .models import ChatCompletionRequest, HealthResponse
from .proxy import proxy_chat_completions

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest) -> JSONResponse:
    result = await proxy_chat_completions(request, body.model_dump())
    return JSONResponse(content=result)


@router.get("/v1/metrics")
async def metrics_snapshot(request: Request) -> dict:
    return await request.app.state.metrics.snapshot()


@router.websocket("/v1/metrics/ws")
async def metrics_ws(websocket: WebSocket) -> None:
    metrics = websocket.app.state.metrics
    await metrics.subscribe(websocket)
    try:
        await websocket.send_text(json.dumps(await metrics.snapshot()))
        while True:
            await websocket.receive_text()  # keep-alive; ignore pings
    except WebSocketDisconnect:
        metrics.unsubscribe(websocket)


@router.get("/v1/audit")
async def audit_log(request: Request) -> list:
    return await request.app.state.audit.all()
