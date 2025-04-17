import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import base64
from typing import List
import json

app = FastAPI()

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
    for block in payload.blocks:
        block_dir = os.path.join(RECEIVED_BLOCKS_DIR, block.id)
        os.makedirs(block_dir, exist_ok=True)
        # Boyutları kaydet
        with open(os.path.join(block_dir, "dimensions.json"), "w", encoding="utf-8") as f:
            json.dump(block.dimensions.dict(), f, ensure_ascii=False, indent=2)
        # Fotoğrafları kaydet
        for photo in block.photos:
            photo_path = os.path.join(block_dir, photo.filename)
            with open(photo_path, "wb") as img_file:
                img_file.write(base64.b64decode(photo.base64))
    return {
        "status": "success",
        "message": f"{len(payload.blocks)} blok başarıyla kaydedildi."
    }

# --- EKLENDİ: Tüm blokları listele ---
@app.get("/blocks/list")
def list_blocks():
    if not os.path.exists(RECEIVED_BLOCKS_DIR):
        return []
    return os.listdir(RECEIVED_BLOCKS_DIR)

# --- EKLENDİ: Bir bloğun dosyalarını listele ---
@app.get("/blocks/{block_id}/files")
def list_block_files(block_id: str):
    block_dir = os.path.join(RECEIVED_BLOCKS_DIR, block_id)
    if not os.path.exists(block_dir):
        raise HTTPException(status_code=404, detail="Blok bulunamadı")
    return os.listdir(block_dir)

# --- EKLENDİ: Dosya indirme endpointi ---
@app.get("/blocks/{block_id}/files/{filename}")
def download_block_file(block_id: str, filename: str):
    block_dir = os.path.join(RECEIVED_BLOCKS_DIR, block_id)
    file_path = os.path.join(block_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    return FileResponse(file_path)

@app.post("/blocks/{block_id}/upload_glb")
def upload_block_glb(block_id: str, file: UploadFile = File(...)):
    block_dir = os.path.join(RECEIVED_BLOCKS_DIR, block_id)
    os.makedirs(block_dir, exist_ok=True)
    glb_path = os.path.join(block_dir, "block.glb")
    with open(glb_path, "wb") as f:
        f.write(file.file.read())
    return {"status": "success", "message": "block.glb başarıyla yüklendi."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
