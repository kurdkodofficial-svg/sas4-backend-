import os
import uuid
import sqlite3
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="SAS4jointJS Backend")

# ڕێگەپێدانی پەیوەندی لە هەموو ماڵپەڕێکەوە (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# دروستکردنی فۆڵدەری وێنەکان ئەگەر نەبێت
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/receipts", StaticFiles(directory=UPLOAD_DIR), name="receipts")

# کلیلی دەسەڵاتی ئەدمین
ADMIN_KEY = "sas4-secret-key-2026"
DB_NAME = "subscribers.db"

# دروستکردنی بنکەدراوەی SQLite
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            amount INTEGER DEFAULT 45000,
            status TEXT DEFAULT 'pending',
            receipt_filename TEXT,
            note TEXT,
            created_at TEXT,
            expires_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.get("/")
def home():
    return {"status": "running", "service": "SAS4jointJS Backend API"}

# ڕێڕەوی وەرگرتنی داواکاری بەشداری نوێ
@app.post("/api/subscribe")
async def subscribe(
    name: str = Form(...),
    phone: str = Form(...),
    note: str = Form(""),
    receipt: UploadFile = File(...)
):
    try:
        # دروستکردنی کۆدی ناسێنەر بۆ بەشداربوو
        now = datetime.now()
        sub_id = f"SAS-{now.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        
        # پاشەکەوتکردنی وێنەی پسوولەکە
        file_ext = os.path.splitext(receipt.filename)[1]
        saved_filename = f"{sub_id}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, saved_filename)
        
        with open(file_path, "wb") as f:
            content = await receipt.read()
            f.write(content)

        # خەزنکردن لە ناو داتابەیس
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO subscribers (id, name, phone, amount, status, receipt_filename, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sub_id, name, phone, 45000, "pending", saved_filename, note, now.isoformat()))
        conn.commit()
        conn.close()

        return {"ok": True, "id": sub_id, "message": "داواکارییەکەت بە سەرکەوتوویی تۆمار کرا"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# هێنانی لیستی بەشداربووان بۆ ئەدمین
@app.get("/api/admin/subscribers")
def get_subscribers(key: str = Query(...)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="کلیلی چوونەژوورەوە هەڵەیە")
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM subscribers ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"ok": True, "subscribers": rows}

# ئەپروڤکردن یان ڕەتکردنەوەی بەشداربوو
@app.post("/api/admin/action")
def update_subscriber_status(sub_id: str = Form(...), action: str = Form(...), key: str = Form(...)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="کلیلی چوونەژوورەوە هەڵەیە")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if action == "approve":
        expires = (datetime.now() + timedelta(days=30)).isoformat()
        cur.execute("UPDATE subscribers SET status = 'active', expires_at = ? WHERE id = ?", (expires, sub_id))
    elif action == "reject":
        cur.execute("UPDATE subscribers SET status = 'rejected' WHERE id = ?", (sub_id,))
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="کردارەکە نادیارە")

    conn.commit()
    conn.close()
    return {"ok": True, "message": "دۆخەکە نوێکرایەوە"}
