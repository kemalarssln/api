import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import base64
from typing import List
import json
import shutil
import time
import threading

app = FastAPI()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
RECEIVED_BLOCKS_DIR = os.path.abspath(os.path.join(BASE_DIR, '../received_blocks'))
PROCESSED_BLOCKS_DIR = os.path.abspath(os.path.join(BASE_DIR, '../processed_blocks'))
os.makedirs(PROCESSED_BLOCKS_DIR, exist_ok=True)

# Ayarlanabilir silme süresi (saniye cinsinden)
PROCESSED_BLOCK_LIFETIME = 5 * 60  # 5 dakika
CLEANUP_INTERVAL = 60  # 60 saniyede bir kontrol

def cleanup_processed_blocks():
    while True:
        now = int(time.time())
        for block_id in os.listdir(PROCESSED_BLOCKS_DIR):
            block_dir = os.path.join(PROCESSED_BLOCKS_DIR, block_id)
            ts_path = os.path.join(block_dir, "timestamp.txt")
            if os.path.exists(ts_path):
                with open(ts_path, "r", encoding="utf-8") as f:
                    try:
                        ts = int(f.read().strip())
                    except Exception:
                        continue
                if now - ts > PROCESSED_BLOCK_LIFETIME:
                    try:
                        shutil.rmtree(block_dir)
                        print(f"Otomatik silindi: {block_id}")
                    except Exception as e:
                        print(f"Silme hatası: {block_id} - {e}")
        time.sleep(CLEANUP_INTERVAL)

# Arka planda otomatik silme görevini başlat
threading.Thread(target=cleanup_processed_blocks, daemon=True).start()

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

@app.get("/processed_blocks/list")
def list_processed_blocks():
    if not os.path.exists(PROCESSED_BLOCKS_DIR):
        return []
    return os.listdir(PROCESSED_BLOCKS_DIR)

# --- EKLENDİ: Bir bloğun dosyalarını listele ---
@app.get("/blocks/{block_id}/files")
def list_block_files(block_id: str):
    block_dir = os.path.join(PROCESSED_BLOCKS_DIR, block_id)
    if not os.path.exists(block_dir):
        raise HTTPException(status_code=404, detail="Blok bulunamadı")
    return os.listdir(block_dir)

# --- EKLENDİ: Dosya indirme endpointi ---
@app.get("/blocks/{block_id}/files/{filename}")
def download_block_file(block_id: str, filename: str):
    block_dir = os.path.join(PROCESSED_BLOCKS_DIR, block_id)
    file_path = os.path.join(block_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    return FileResponse(file_path)

@app.delete("/blocks/{block_id}")
def delete_block(block_id: str):
    block_dir = os.path.join(PROCESSED_BLOCKS_DIR, block_id)
    if not os.path.exists(block_dir):
        raise HTTPException(status_code=404, detail="Blok bulunamadı")
    try:
        shutil.rmtree(block_dir)
        return {"status": "success", "message": f"Blok {block_id} ve tüm dosyaları silindi."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Silme hatası: {e}")

@app.post("/blocks/{block_id}/upload_glb")
def upload_block_glb(block_id: str, file: UploadFile = File(...)):
    block_dir = os.path.join(RECEIVED_BLOCKS_DIR, block_id)
    processed_dir = os.path.join(PROCESSED_BLOCKS_DIR, block_id)
    os.makedirs(processed_dir, exist_ok=True)
    glb_path = os.path.join(processed_dir, "block.glb")
    with open(glb_path, "wb") as f:
        f.write(file.file.read())
    # Zaman damgası kaydet
    with open(os.path.join(processed_dir, "timestamp.txt"), "w", encoding="utf-8") as f:
        f.write(str(int(time.time())))
    # Ham blok klasörünü sil
    if os.path.exists(block_dir):
        shutil.rmtree(block_dir)
    return {"status": "success", "message": f"block.glb işlenmiş olarak kaydedildi: {block_id}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
