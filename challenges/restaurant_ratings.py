import asyncio
import logging
import pprint
import time
from typing import Annotated

import httpx
import orjson
import uvloop
from pydantic import BaseModel, Field, PositiveFloat, PositiveInt
from retrying import retry

"""Return a list of top-rated restaurants in a given city.

Return a list of up to five restaurant names for a given city, which all 
have the highest average rating. For example, if a city's highest-rated
restaurant has an average rating of 4.7 stars, return only up to five
total restaurants that also have 4.7 stars.
"""

CITY = "seattle"
BASE_URL = "https://jsonmock.hackerrank.com/api/food_outlets"


logging.basicConfig(level=logging.DEBUG)

AvgRating = Annotated[PositiveFloat, Field(ge=0.0, le=5.0)]


# Modeling data in Pydantic offers robust data validation, and the convenience of working
# with objects, for a modest performance penalty.
class RestaurantData(BaseModel):
    city: str
    estimated_cost: PositiveInt
    id: PositiveInt
    name: str
    average_rating: AvgRating
    votes: PositiveInt


class APIResponse(BaseModel):
    data: list[RestaurantData]
    page: PositiveInt
    per_page: PositiveInt
    total: PositiveInt
    total_pages: PositiveInt


def retry_if_request_error(exception: Exception) -> bool:
    """Only retry requests for RequestErrors.

    RequestErrors are the only superclass of errors that might be transient
    and could potentially benefit from retry logic. All other exceptions should
    be raised.

    See HTTPX exception hierarchy for more info:
    https://www.python-httpx.org/exceptions/
    """
    return isinstance(exception, httpx.RequestError)


# Exponential backoff for failures, up to three attempts, only for RequestErrors.
@retry(
    wait_exponential_multiplier=1000,
    stop_max_attempt_number=3,
    retry_on_exception=retry_if_request_error,
)
async def api_call(client: httpx.AsyncClient, city: str, page: int = 1) -> APIResponse:
    """Make an API call for a single page of data for a given city.

    Args:
        client: Open instance of httpx.AsyncClient.
        city: Name of the city to retrieve restaurant data for.
        page: Page of data to retrieve. Defaults to 1.

    Returns:
        An APIResponse model based on to the data structure returned by the API.

    Raises:
        - httpx.HTTPError if status code is not 2XX
        - ValueError if no data found in the response.

    """
    params = {"city": city, "page": page}
    response = await client.get(url=BASE_URL, params=params)
    response.raise_for_status()
    # orjson is faster and more correct than the native Python json module.
    # https://github.com/ijl/orjson
    json = orjson.loads(response.content)
    if not json["data"]:
        raise ValueError(f'No restaurant data found for city "{city}"')

    data = [
        RestaurantData(
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


async def get_restaurant_data(city: str) -> list[RestaurantData]:
    """Get all restaurant data for a given city.

    Retrieves all pages of restaurant data and concatenates results
    into a single list, which is then returned.

    Args:
        city: Name of the city to retrieve restaurant data for.

    Returns:
        A list of restaurant data for the given city.

    Raises:
        N/A

    """
    # An AsyncClient uses connection pooling to reduce overhead.
    # HTTP/2 uses multiplexing, compressed headers, etc. to improve performance.
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=10)
    async with httpx.AsyncClient(http2=True, limits=limits) as client:
        response = await api_call(client=client, city=city, page=1)
        # In production, I would prefer to amend the API to return all results in
        # a single request. Assuming that's not possible, request all
        # pages asynchronously.
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
    """Get restaurants in a city that all share the highest average rating.

    I.e., if the highest rated restaurant in a city has 4.7 stars, only restaurants
    that also have 4.7 star average ratings will be returned.

    Args:
        city: Name of the city to retrieve restaurant data for.
        limit: Maximum number of restaurants to list.

    Returns:
        A list of restaurant names that all share the highest average rating.

    Raises:
        N/A

    """
    data = await get_restaurant_data(city=city)
    sorted_data = sorted(data, key=lambda d: d.average_rating, reverse=True)
    highest_rating = sorted_data[0].average_rating
    return [x.name for x in sorted_data if x.average_rating == highest_rating][:limit]


if __name__ == "__main__":
    # UVloop is a fast, drop-in replacement for the default event loop. Performance
    # is comparable to golang.
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    start_time = time.perf_counter()
    results = asyncio.run(get_highest_rated_restaurants(city=CITY))
    end_time = time.perf_counter()
    running_time = end_time - start_time
    pprint.pprint(results)
    print(f"Running time: {running_time:4f}")
