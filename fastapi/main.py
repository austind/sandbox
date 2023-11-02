"""
https://fastapi.tiangolo.com/#example
"""
from typing import Optional, Union

from pydantic import BaseModel

from fastapi import FastAPI

app = FastAPI()


class Item(BaseModel):
    id: int
    name: str
    price: float
    is_offer: Optional[bool]


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


@app.put("/items/{item_id}")
def save_item(item: Item):
    return {"item_name": item.name, "item_price": item.price, "item_id": item.id}
