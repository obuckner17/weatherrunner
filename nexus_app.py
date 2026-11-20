import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from nexus_engine import get_s3_client, run_verified_agent

app = FastAPI(title="WEATHER RUNNER")

class QueryPayload(BaseModel):
    prompt: str
    object_key: str = ""
    pacing_sec: float = 6.0

@app.get("/")
async def index():
    return FileResponse("nexus_ui.html")

@app.get("/api/status")
async def status():
    return {
        "inference_configured": bool(os.getenv("AKAMAI_API_KEY")),
        "model": os.getenv("CHAT_MODEL", "qwen3-8-27b"),
        "object_storage_configured": bool(os.getenv("OBJ_BUCKET") and os.getenv("OBJ_ACCESS_KEY")),
        "bucket": os.getenv("OBJ_BUCKET", "not-set")
    }

@app.get("/api/files")
async def list_files():
    try:
        s3 = get_s3_client()
        bucket = os.environ["OBJ_BUCKET"]
        resp = s3.list_objects_v2(Bucket=bucket)
        keys = [item["Key"] for item in resp.get("Contents", [])]
        return {"bucket": bucket, "files": keys}
    except Exception as e:
        return {"bucket": "error", "files": [], "detail": str(e)}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        s3 = get_s3_client()
        bucket = os.environ["OBJ_BUCKET"]
        body = await file.read()
        s3.put_object(Bucket=bucket, Key=file.filename, Body=body)
        return {"uploaded": file.filename, "bytes": len(body)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/run")
async def run_pipeline(payload: QueryPayload):
    try:
        return run_verified_agent(payload.prompt, payload.object_key, payload.pacing_sec)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
