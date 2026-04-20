import os
import pickle
import subprocess

import jwt
import requests
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse


app = FastAPI()


@app.post("/run")
async def run_command(request: Request):
    body = await request.json()
    user_command = body.get("cmd", "")
    return subprocess.run(f"sh -c '{user_command}'", shell=True, capture_output=True, text=True).stdout


@app.post("/decode-token")
async def decode_token(request: Request):
    body = await request.json()
    token = body.get("token", "")
    return jwt.decode(token, options={"verify_signature": False}, algorithms=["none", "HS256"])


@app.get("/fetch")
async def fetch_remote(request: Request):
    target_url = request.query_params.get("url", "")
    return requests.get(target_url, timeout=10).text


@app.get("/download")
async def download_file(request: Request):
    requested_path = request.query_params.get("file", "")
    full_path = os.path.join("exports", requested_path)
    return FileResponse(full_path)


@app.post("/restore")
async def restore_state(request: Request):
    body = await request.body()
    return pickle.loads(body)


@app.post("/parse-yaml")
async def parse_yaml(request: Request):
    body = await request.body()
    return yaml.load(body, Loader=yaml.Loader)
