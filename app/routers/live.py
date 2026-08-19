import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["live"])

# Set of active subscriber queues for SSE notifications
sse_subscribers: set = set()

async def notify_live_subscribers(table_name: str = "all"):
    """
    Broadcast a 'change' event to all connected SSE client streams.
    """
    for queue in list(sse_subscribers):
        try:
            await queue.put(f"event: change\ndata: {{\"table\":\"{table_name}\"}}\n\n")
        except Exception:
            pass

@router.get("/api/live")
async def live_stream(request: Request):
    """
    Server-Sent Events (SSE) endpoint for real-time table sync updates.
    """
    queue = asyncio.Queue()
    sse_subscribers.add(queue)

    async def event_generator():
        try:
            # Send initial ping event upon connection
            yield "event: ping\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Wait for change notification or timeout after 15s to send keep-alive heartbeat
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield message
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            sse_subscribers.discard(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
