from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

# Создаем таблицы (добавлено поле created_at для отслеживания времени)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        name TEXT,
        username TEXT,
        room TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT, author TEXT, author_id INTEGER, type TEXT, time TEXT, price INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

# Модели Pydantic
class UserSync(BaseModel):
    telegram_id: int
    name: str
    username: str | None = None

class ProfileUpdate(BaseModel):
    telegram_id: int
    room: str

class Order(BaseModel):
    text: str
    author: str
    author_id: int
    type: str
    time: str
    price: int | None = None

# 1. Авторизация / Синхронизация профиля
@app.post("/sync_user")
def sync_user(user: UserSync):
    cursor.execute("""
        INSERT INTO users (telegram_id, name, username)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET name=?, username=?
    """, (user.telegram_id, user.name, user.username, user.name, user.username))
    conn.commit()
    
    cursor.execute("SELECT room FROM users WHERE telegram_id = ?", (user.telegram_id,))
    row = cursor.fetchone()
    return {"room": row[0] if row and row[0] else ""}

# 2. Обновление доп. инфо (комната)
@app.post("/update_profile")
def update_profile(data: ProfileUpdate):
    cursor.execute("UPDATE users SET room = ? WHERE telegram_id = ?", (data.room, data.telegram_id))
    conn.commit()
    return {"status": "ok"}

# 3. Публикация заказа с привязкой ID
@app.post("/add_order")
def add_order(order: Order):
    cursor.execute("""
        INSERT INTO orders (text, author, author_id, type, time, price)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (order.text, order.author, order.author_id, order.type, order.time, order.price))
    conn.commit()
    return {"status": "ok"}

# 4. Получение ВСЕХ заказов (Лента: только свежие, автоудаление старых)
@app.get("/orders")
def get_orders():
    # Очистка базы от заказов старше 2 дней
    cursor.execute("DELETE FROM orders WHERE created_at <= datetime('now', '-2 days')")
    conn.commit()

    # Выдача объявлений, которым меньше 1 дня
    cursor.execute("""
        SELECT id, text, author, author_id, type, time, price 
        FROM orders 
        WHERE created_at > datetime('now', '-1 day')
        ORDER BY id DESC
    """)
    columns = ["id", "text", "author", "author_id", "type", "time", "price"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# 5. Мои объявления (Профиль: все заказы пользователя с флагом архива)
@app.get("/my_orders/{telegram_id}")
def get_my_orders(telegram_id: int):
    # Очистка базы от заказов старше 2 дней
    cursor.execute("DELETE FROM orders WHERE created_at <= datetime('now', '-2 days')")
    conn.commit()

    # Выдача всех записей с вычислением флага is_archived
    cursor.execute("""
        SELECT id, text, type, time, price, 
               CASE WHEN created_at <= datetime('now', '-1 day') THEN 1 ELSE 0 END as is_archived
        FROM orders 
        WHERE author_id = ? 
        ORDER BY id DESC
    """, (telegram_id,))
    
    columns = ["id", "text", "type", "time", "price", "is_archived"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# 6. Удаление объявления
@app.delete("/delete_order/{order_id}")
def delete_order(order_id: int):
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)