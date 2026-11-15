import os
import json
import time
import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from security import rate_limit, verify_access
from db import init_db, add_message, get_messages

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ai-chat")

app = FastAPI(title="AI Chat")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

init_db()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


def call_llm(messages, retries=3):
    last_error = None

    for i in range(retries):
        try:
            return client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                timeout=30,
                max_tokens=512,
            )
        except Exception as e:
            last_error = e
            logger.warning("LLM failed attempt=%s error=%s", i + 1, e)
            if i < retries - 1:
                time.sleep(2 ** i)

    raise last_error


def build_messages(session_id: str, user_message: str):
    history = get_messages(session_id, limit=10)
    messages = [{"role": "system", "content": "你是一个简洁的中文助手。"}]
    messages += history
    messages.append({"role": "user", "content": user_message})
    return messages


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug/access")
def debug_access():
    return {"has_access_code": bool(os.getenv("ACCESS_CODE", "").strip())}


@app.post("/chat")
def chat(req: ChatRequest, request: Request, _=Depends(verify_access)):
    rate_limit(request)

    if len(req.message) > 2000:
        raise HTTPException(status_code=400, detail="message too long")
    if len(req.session_id) > 64:
        raise HTTPException(status_code=400, detail="session_id too long")

    messages = build_messages(req.session_id, req.message)

    start = time.time()
    try:
        resp = call_llm(messages)
    except Exception:
        logger.exception("chat failed session=%s", req.session_id)
        raise HTTPException(status_code=502, detail="LLM request failed")

    reply = resp.choices[0].message.content
    add_message(req.session_id, "user", req.message)
    add_message(req.session_id, "assistant", reply)

    usage = getattr(resp, "usage", None)
    logger.info(
        "chat session=%s elapsed=%.2fs tokens=%s",
        req.session_id,
        time.time() - start,
        getattr(usage, "total_tokens", None) if usage else None,
    )

    return {"reply": reply, "session_id": req.session_id}


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request, _=Depends(verify_access)):
    rate_limit(request)

    if len(req.message) > 2000:
        raise HTTPException(status_code=400, detail="message too long")
    if len(req.session_id) > 64:
        raise HTTPException(status_code=400, detail="session_id too long")

    messages = build_messages(req.session_id, req.message)

    def gen():
        start = time.time()
        reply_parts = []
        stream = None
        last_error = None

        for attempt in range(3):
            try:
                stream = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    stream=True,
                    timeout=30,
                    max_tokens=512,
                )
                break
            except Exception as e:
                last_error = e
                logger.warning(
                    "stream create failed attempt=%s error=%s",
                    attempt + 1,
                    e,
                )
                if attempt < 2:
                    time.sleep(2 ** attempt)

        if stream is None:
            logger.error("stream failed session=%s error=%s", req.session_id, last_error)
            payload = json.dumps({"error": "LLM request failed"}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    reply_parts.append(delta)
                    payload = json.dumps({"delta": delta}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
        except Exception:
            logger.exception("stream interrupted session=%s", req.session_id)
            payload = json.dumps({"error": "stream interrupted"}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        finally:
            reply = "".join(reply_parts)
            if reply:
                add_message(req.session_id, "user", req.message)
                add_message(req.session_id, "assistant", reply)

            logger.info(
                "stream session=%s elapsed=%.2fs chars=%s",
                req.session_id,
                time.time() - start,
                len(reply),
            )

        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/history/{session_id}")
def history(session_id: str, _=Depends(verify_access)):
    return {"messages": get_messages(session_id, limit=50)}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")