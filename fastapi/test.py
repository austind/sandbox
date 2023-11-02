""" Test PUT data to a the FastAPI endpoint defined in main.py """
from typing import Optional

import httpx
import ipdb
from pydantic import BaseModel


class Item(BaseModel):
    id: int
    name: str
    price: float
    is_offer: Optional[bool] = None


def main():
    item = Item(id=1, name="MacBook Pro", price=2700.0)
    resp = httpx.put("http://127.0.0.1:8000/items/1", data=item.model_dump_json())
    ipdb.set_trace()


if __name__ == "__main__":
    main()
