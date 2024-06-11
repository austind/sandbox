import asyncio
import pprint
from typing import Annotated

import httpx
import uvloop
from pydantic import BaseModel, Field, PositiveFloat, PositiveInt

"""Return a list of top-rated restaurants in a given city.

Return a list of up to five restaurant names for a given city, which all 
have the highest average rating. For example, if a city's highest-rated
restaurant has an average rating of 4.7 stars, return only up to five
total restaurants that also have 4.7 stars.
"""

CITY = "seattle"
BASE_URL = "https://jsonmock.hackerrank.com/api/food_outlets"


# logging.basicConfig(handlers=[logging.StreamHandler()], level=logging.DEBUG)

AvgRating = Annotated[PositiveFloat, Field(ge=0.0, le=5.0)]

# Modeling data in Pydantic offers robust data validation and the convenience of working
# with objects for a modest performance penalty.
class APIData(BaseModel):
    city: str
    estimated_cost: PositiveInt
    id: PositiveInt
    name: str
    average_rating: AvgRating
    votes: PositiveInt


class APIResponse(BaseModel):
    data: list[APIData]
    page: PositiveInt
    per_page: PositiveInt
    total: PositiveInt
    total_pages: PositiveInt


async def api_call(client: httpx.AsyncClient, city: str, page: int = 1) -> APIResponse:
    """Make an API call to retrieve a single page of data for a given city.

    Args:
        client: Open instance of httpx.AsyncClient to use.
        city: Name of the city to retrieve restaurant data for.
        page: Page of data to retrieve. Defaults to 1.

    Returns:
        An unmodified dict of API results.

    Raises:
        - httpx.HTTPError if status code is not 2XX
        - ValueError if no data found in the response.

    """
    params = {"city": city, "page": page}
    response = await client.get(url=BASE_URL, params=params)
    response.raise_for_status()
    json = response.json()
    if not json["data"]:
        raise ValueError(f'No restaurant data found for city "{city}"')

    data = [
        APIData(
            city=x["city"],
            estimated_cost=x["estimated_cost"],
            name=x["name"],
            id=x["id"],
            average_rating=x["user_rating"]["average_rating"],
            votes=x["user_rating"]["votes"],
        )
        for x in json["data"]
    ]
    return APIResponse(
        page=json["page"],
        per_page=json["per_page"],
        total=json["total"],
        total_pages=json["total_pages"],
        data=data,
    )


async def get_restaurant_data(city: str) -> list[APIData]:
    """Get all pages of restaurant data for a given city.

    Retrieves all pages of restaurant data and concatenates results
    into a single list, which is then returned.

    Args:
        city: Name of the city to retrieve restaurant data for.

    Returns:
        A list of all restaurant data for the given city.

    Raises:
        N/A

    """
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=10)
    async with httpx.AsyncClient(http2=True, limits=limits) as client:
        response = await api_call(client=client, city=city, page=1)
        if response.total_pages > 1:
            tasks = [
                api_call(client=client, city=city, page=page)
                for page in range(2, response.total_pages + 1)
            ]
            page_data = await asyncio.gather(*tasks)
            for page in page_data:
                response.data.extend(page.data)
        return response.data


async def get_highest_rated_restaurants(city: str, limit: int = 5) -> list[str]:
    """Get the N restaurants in a given city that all share the highest rating.

    For example: if the highest rated restaurant in a city has 4.7 stars,
    only restaurants that also have 4.7 star ratings (up to limit) will be returned.

    Args:
        city: Name of the city to retrieve restaurant data for.
        limit: Maximum number of restaurants to list.

    Returns:
        A list of restaurants that all share the highest rating.

    Raises:
        N/A

    """
    data = await get_restaurant_data(city=city)
    sorted_data = sorted(data, key=lambda d: d.average_rating, reverse=True)
    highest_rating = sorted_data[0].average_rating
    return [x.name for x in sorted_data if x.average_rating == highest_rating][:limit]


if __name__ == "__main__":
    # UVloop is a fast, drop-in replacement for the default event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    results = asyncio.run(get_highest_rated_restaurants(city=CITY))
    pprint.pprint(results)
