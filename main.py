from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3

app = FastAPI()

# Разрешаем запросы из браузера
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT, author TEXT, type TEXT, time TEXT, price INTEGER
    )
""")
conn.commit()

class Order(BaseModel):
    text: str
    author: str
    type: str
    time: str
    price: int | None = None

@app.post("/add_order")
def add_order(order: Order):
    cursor.execute("INSERT INTO orders (text, author, type, time, price) VALUES (?, ?, ?, ?, ?)",
                   (order.text, order.author, order.type, order.time, order.price))
    conn.commit()
    return {"status": "ok"}

@app.get("/orders")
def get_orders():
    cursor.execute("SELECT id, text, author, type, time, price FROM orders ORDER BY id DESC")
    columns = ["id", "text", "author", "type", "time", "price"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)