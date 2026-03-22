from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.agent import build_agent, WORKSPACE_DIR
import json
import uuid

agent = build_agent()

app = FastAPI(title="Corporate IntelliOps Agent API")

class ResearchRequest(BaseModel):
    query: str

def _extract_text(content) -> str:
    """Extract plain text from an AIMessageChunk content (str or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""

def _clear_workspace():
    for f in WORKSPACE_DIR.glob("*.md"):
        f.unlink(missing_ok=True)

@app.post("/research/stream")
async def research_stream(request: ResearchRequest):
    async def event_stream():
        yield ": connected\n\n"
        _clear_workspace()
        try:
            pending_tool_calls: dict[int, dict] = {}  # index → {id, name, args}

            async for chunk, _ in agent.astream(
                {"messages": [{"role": "user", "content": request.query}]},
                config={"configurable": {"thread_id": str(uuid.uuid4())}},
                stream_mode="messages",
            ):
                msg_type = chunk.__class__.__name__

                if msg_type == "AIMessageChunk":
                    # Stream text tokens
                    text = _extract_text(chunk.content)
                    if text:
                        yield f"event: token\ndata: {json.dumps({'content': text})}\n\n"

                    # Accumulate tool call chunks by index
                    for tc in getattr(chunk, "tool_call_chunks", []):
                        idx = tc.get("index", 0)
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {"name": tc.get("name", ""), "args": ""}
                        if tc.get("name"):
                            pending_tool_calls[idx]["name"] = tc["name"]
                        if tc.get("args"):
                            pending_tool_calls[idx]["args"] += tc["args"]

                elif msg_type == "ToolMessage":
                    # Emit all accumulated tool calls before the result
                    for idx in sorted(pending_tool_calls.keys()):
                        tc = pending_tool_calls[idx]
                        try:
                            args = json.loads(tc["args"]) if tc["args"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield f"event: tool_call\ndata: {json.dumps({'tool': tc['name'], 'input': args})}\n\n"
                    pending_tool_calls = {}

                    content = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    yield f"event: tool_result\ndata: {json.dumps({'tool': chunk.name, 'content': content[:300]})}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

        finally:
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
