import os
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from security import verify_access, rate_limit

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


@app.post("/chat")
def chat(req: ChatRequest, request: Request, _=Depends(verify_access)):
    rate_limit(request)

    if len(req.message) > 2000:
        raise HTTPException(status_code=400, detail="message too long")

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": req.message}],
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
            messages=[{"role": "user", "content": req.message}],
            stream=True,
            timeout=30,
            max_tokens=512,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")