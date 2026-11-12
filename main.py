import os
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

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
def chat(req: ChatRequest):
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": req.message}],
        timeout=30,
    )
    return {"reply": resp.choices[0].message.content}


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    def gen():
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": req.message}],
            stream=True,
            timeout=30,
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