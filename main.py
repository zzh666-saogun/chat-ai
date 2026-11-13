import os
import json

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from security import rate_limit, verify_access

load_dotenv()

app = FastAPI(title="AI Chat")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


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

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一个简洁的中文助手。"},
            {"role": "user", "content": req.message},
        ],
        timeout=30,
        max_tokens=512,
    )
    return {"reply": resp.choices[0].message.content}


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request, _=Depends(verify_access)):
    rate_limit(request)

    if len(req.message) > 2000:
        raise HTTPException(status_code=400, detail="message too long")

    def gen():
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个简洁的中文助手。"},
                {"role": "user", "content": req.message},
            ],
            stream=True,
            timeout=30,
            max_tokens=512,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                payload = json.dumps({"delta": delta}, ensure_ascii=False)
                yield f"data: {payload}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")