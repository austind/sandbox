"""
https://fastapi.tiangolo.com/#example
"""

from models import Item

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


@app.put("/items/{item_id}")
def save_item(item: Item):
    return {"item_name": item.name, "item_price": item.price, "item_id": item.id}
