import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
from typing import List, Dict
import subprocess
import json

app = FastAPI()

# Kayıtların her zaman doğru yerde olması için tam yol
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
RECEIVED_BLOCKS_DIR = os.path.abspath(os.path.join(BASE_DIR, '../received_blocks'))

class BlockPhoto(BaseModel):
    filename: str
    base64: str

class BlockDimensions(BaseModel):
    width: float
    height: float
    length: float

class BlockPayload(BaseModel):
    id: str
    customId: str
    dimensions: BlockDimensions
    photos: List[BlockPhoto]

class BlocksPayload(BaseModel):
    blocks: List[BlockPayload]

@app.get("/")
def read_root():
    return {"message": "Blender API çalışıyor!"}

@app.post("/blocks")
def receive_blocks(payload: BlocksPayload):
    os.makedirs(RECEIVED_BLOCKS_DIR, exist_ok=True)
    glb_paths = []
    for block in payload.blocks:
        block_dir = os.path.join(RECEIVED_BLOCKS_DIR, block.id)
        os.makedirs(block_dir, exist_ok=True)
        # Boyutları kaydet
        with open(os.path.join(block_dir, "dimensions.json"), "w", encoding="utf-8") as f:
            json.dump({
                "id": block.id,
                "customId": block.customId,
                "dimensions": {
                    "width": block.dimensions.width,
                    "height": block.dimensions.height,
                    "length": block.dimensions.length
                }
            }, f, ensure_ascii=False, indent=2)
        # Fotoğrafları kaydet
        for photo in block.photos:
            photo_path = os.path.join(block_dir, photo.filename)
            with open(photo_path, "wb") as img_file:
                img_file.write(base64.b64decode(photo.base64))
        # Blender scriptini çağır
        blender_path = "blender"  # Eğer sistemde path'te yoksa tam yol verilebilir
        script_path = os.path.abspath(os.path.join(BASE_DIR, "blender_create_block.py"))
        block_dir_abs = os.path.abspath(block_dir)
        cmd = [
            blender_path,
            "--background",
            "--python", script_path,
            "--",
            f"--block_dir={block_dir_abs}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        glb_path = os.path.join(block_dir_abs, "block.glb")
        log_path = os.path.join(block_dir_abs, "blender_script_log.txt")
        # Logları kaydet
        with open(os.path.join(block_dir_abs, "backend_blender_stdout.txt"), "w", encoding="utf-8") as f:
            f.write(result.stdout)
        with open(os.path.join(block_dir_abs, "backend_blender_stderr.txt"), "w", encoding="utf-8") as f:
            f.write(result.stderr)
        if not os.path.exists(glb_path):
            error_msg = f"Blender .glb dosyası oluşturulamadı!\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    error_msg += f"\nBlender script log:\n{f.read()}"
            raise HTTPException(status_code=500, detail=error_msg)
        glb_paths.append(glb_path)
    return {
        "status": "success",
        "message": f"{len(payload.blocks)} blok başarıyla kaydedildi ve .glb dosyası oluşturuldu.",
        "glb_paths": glb_paths
    }

# Render için: PORT environment variable'ını kullan!
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
