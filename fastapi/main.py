"""
https://fastapi.tiangolo.com/#example
"""

from typing import Annotated

from models import Item

from fastapi import FastAPI, Query

app = FastAPI()


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/items/")
async def read_items(q: Annotated[str | None, Query(max_length=50)] = None):
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


@app.put("/items/{item_id}")
async def save_item(item: Item):
    return {"item_name": item.name, "item_price": item.price, "item_id": item.id}
