from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import sqlite3
import os
import urllib.request
import urllib.parse
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conn = sqlite3.connect("orders.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# ------------------------- БАЗА ДАННЫХ -------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT,
    room TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT,
    author TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    time TEXT,
    price INTEGER NOT NULL DEFAULT 0,
    title TEXT,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Миграция существующей базы: новые поля добавляются без удаления старых.
def ensure_column(table: str, column: str, definition: str):
    cols = {row["name"] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

ensure_column("orders", "title", "TEXT")
ensure_column("orders", "description", "TEXT")

cursor.execute("""
CREATE TABLE IF NOT EXISTS order_responders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    telegram_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(order_id, telegram_id),
    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
)
""")

conn.commit()

# Перенос старых объявлений: прежний text становится description.
cursor.execute("""
UPDATE orders
SET
    title = COALESCE(NULLIF(title, ''), 'Объявление'),
    description = COALESCE(NULLIF(description, ''), COALESCE(text, ''))
WHERE title IS NULL OR title = '' OR description IS NULL OR description = ''
""")
conn.commit()

# ------------------------- МОДЕЛИ -------------------------

class UserSync(BaseModel):
    telegram_id: int
    name: str
    username: str | None = None

class ProfileUpdate(BaseModel):
    telegram_id: int
    room: str

class OrderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    author: str = Field(min_length=1, max_length=120)
    author_id: int
    type: str = Field(min_length=1, max_length=40)
    price: int = Field(ge=0, le=2_000_000_000)

class RespondRequest(BaseModel):
    telegram_id: int
    name: str | None = None
    username: str | None = None

class RefuseRequest(BaseModel):
    telegram_id: int

# ------------------------- УВЕДОМЛЕНИЯ TELEGRAM -------------------------

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def send_telegram_message(telegram_id: int, text: str) -> bool:
    """
    Отправляет сообщение через Telegram Bot API.
    Чтобы это стало реальным пуш-уведомлением, задай переменную окружения:
    TELEGRAM_BOT_TOKEN=<токен бота>
    """
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN не задан — уведомление не отправлено.")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": str(telegram_id),
            "text": text,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        return bool(data.get("ok"))
    except Exception as e:
        print(f"Ошибка Telegram notification: {e}")
        return False

# ------------------------- ПРОФИЛЬ -------------------------

@app.post("/sync_user")
def sync_user(user: UserSync):
    cursor.execute("""
        INSERT INTO users (telegram_id, name, username)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            name=excluded.name,
            username=excluded.username
    """, (user.telegram_id, user.name, user.username))
    conn.commit()

    row = cursor.execute(
        "SELECT room FROM users WHERE telegram_id = ?",
        (user.telegram_id,)
    ).fetchone()
    return {"room": row["room"] if row and row["room"] else ""}

@app.post("/update_profile")
def update_profile(data: ProfileUpdate):
    cursor.execute(
        "UPDATE users SET room = ? WHERE telegram_id = ?",
        (data.room, data.telegram_id)
    )
    conn.commit()
    return {"status": "ok"}

# ------------------------- ОБЪЯВЛЕНИЯ -------------------------

def cleanup_old_orders():
    cursor.execute("DELETE FROM orders WHERE created_at <= datetime('now', '-2 days')")
    conn.commit()

@app.post("/add_order")
def add_order(order: OrderCreate):
    if order.price < 0:
        raise HTTPException(status_code=400, detail="Цена не может быть отрицательной.")

    cursor.execute("""
        INSERT INTO orders (
            title, description, text, author, author_id, type, time, price
        )
        VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
    """, (
        order.title.strip(),
        order.description.strip(),
        order.description.strip(),
        order.author.strip(),
        order.author_id,
        order.type.strip(),
        order.price,
    ))
    conn.commit()
    return {"status": "ok", "id": cursor.lastrowid}

def order_summary_rows():
    return cursor.execute("""
        SELECT
            o.id,
            o.title,
            o.description,
            o.author,
            o.author_id,
            o.type,
            o.price,
            COUNT(r.id) AS response_count
        FROM orders o
        LEFT JOIN order_responders r ON r.order_id = o.id
        WHERE o.created_at > datetime('now', '-1 day')
        GROUP BY o.id
        ORDER BY o.id DESC
    """).fetchall()

@app.get("/orders")
def get_orders():
    cleanup_old_orders()
    result = []

    for row in order_summary_rows():
        result.append({
            "id": row["id"],
            "title": row["title"] or "Объявление",
            "description": row["description"] or "",
            "author": row["author"],
            "author_id": row["author_id"],
            "type": row["type"],
            "price": row["price"],
            "response_count": row["response_count"],
        })

    return result

@app.get("/orders/{order_id}")
def get_order(order_id: int, viewer_id: int | None = None):
    cleanup_old_orders()

    row = cursor.execute("""
        SELECT
            o.id, o.title, o.description, o.author, o.author_id, o.type, o.price,
            u.username AS author_username
        FROM orders o
        LEFT JOIN users u ON u.telegram_id = o.author_id
        WHERE o.id = ?
    """, (order_id,)).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Объявление не найдено.")

    responders = cursor.execute("""
        SELECT
            r.telegram_id,
            COALESCE(u.name, 'Пользователь') AS name,
            u.username,
            u.room
        FROM order_responders r
        LEFT JOIN users u ON u.telegram_id = r.telegram_id
        WHERE r.order_id = ?
        ORDER BY r.created_at ASC, r.id ASC
    """, (order_id,)).fetchall()

    current_user_responded = False
    if viewer_id is not None:
        current_user_responded = cursor.execute("""
            SELECT 1
            FROM order_responders
            WHERE order_id = ? AND telegram_id = ?
        """, (order_id, viewer_id)).fetchone() is not None

    return {
        "id": row["id"],
        "title": row["title"] or "Объявление",
        "description": row["description"] or "",
        "author": row["author"],
        "author_id": row["author_id"],
        "author_username": row["author_username"],
        "type": row["type"],
        "price": row["price"],
        "response_count": len(responders),
        "current_user_responded": current_user_responded,
        "responders": [dict(r) for r in responders],
    }

# ------------------------- ОТКЛИКИ -------------------------

@app.post("/orders/{order_id}/respond")
def respond_to_order(order_id: int, data: RespondRequest):
    cleanup_old_orders()

    order = cursor.execute("""
        SELECT id, title, author, author_id, price
        FROM orders
        WHERE id = ?
    """, (order_id,)).fetchone()

    if not order:
        raise HTTPException(status_code=404, detail="Объявление не найдено.")

    if order["author_id"] == data.telegram_id:
        raise HTTPException(status_code=400, detail="Нельзя откликнуться на своё объявление.")

    existing = cursor.execute("""
        SELECT 1 FROM order_responders
        WHERE order_id = ? AND telegram_id = ?
    """, (order_id, data.telegram_id)).fetchone()

    if existing:
        raise HTTPException(status_code=409, detail="Вы уже откликались на это объявление.")

    # Синхронизируем данные исполнителя перед записью отклика.
    if data.name is not None or data.username is not None:
        cursor.execute("""
            INSERT INTO users (telegram_id, name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                name=COALESCE(excluded.name, users.name),
                username=COALESCE(excluded.username, users.username)
        """, (
            data.telegram_id,
            data.name or "Пользователь",
            data.username,
        ))

    cursor.execute("""
        INSERT INTO order_responders (order_id, telegram_id)
        VALUES (?, ?)
    """, (order_id, data.telegram_id))
    conn.commit()

    responder = cursor.execute("""
        SELECT name, username
        FROM users
        WHERE telegram_id = ?
    """, (data.telegram_id,)).fetchone()

    responder_name = responder["name"] if responder else "Пользователь"
    responder_username = responder["username"] if responder else None

    notification_text = (
        f"На ваше объявление «{order['title']}» откликнулся исполнитель.\n"
        f"Имя: {responder_name}"
    )
    if responder_username:
        notification_text += f"\nUsername: {responder_username}"
    notification_text += "\n\nОткройте приложение, чтобы посмотреть всех откликнувшихся."

    notification_sent = send_telegram_message(order["author_id"], notification_text)

    return {
        "status": "ok",
        "notification_sent": notification_sent,
        "message": "Отклик сохранён."
    }

@app.delete("/orders/{order_id}/respond")
def refuse_from_order(order_id: int, data: RefuseRequest):
    cursor.execute("""
        DELETE FROM order_responders
        WHERE order_id = ? AND telegram_id = ?
    """, (order_id, data.telegram_id))
    conn.commit()

    return {"status": "ok"}

# ------------------------- МОИ ОБЪЯВЛЕНИЯ -------------------------

@app.get("/my_orders/{telegram_id}")
def get_my_orders(telegram_id: int):
    cleanup_old_orders()

    rows = cursor.execute("""
        SELECT
            o.id,
            o.title,
            o.description,
            o.type,
            o.price,
            CASE WHEN o.created_at <= datetime('now', '-1 day') THEN 1 ELSE 0 END AS is_archived,
            COUNT(r.id) AS response_count
        FROM orders o
        LEFT JOIN order_responders r ON r.order_id = o.id
        WHERE o.author_id = ?
        GROUP BY o.id
        ORDER BY o.id DESC
    """, (telegram_id,)).fetchall()

    return [dict(row) for row in rows]

@app.delete("/delete_order/{order_id}")
def delete_order(order_id: int):
    cursor.execute("DELETE FROM order_responders WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    return {"status": "ok"}

@app.post("/restore_order/{order_id}")
def restore_order(order_id: int):
    cursor.execute(
        "UPDATE orders SET created_at = CURRENT_TIMESTAMP WHERE id = ?",
        (order_id,)
    )
    conn.commit()
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
