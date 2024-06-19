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

CITY = "denver"
BASE_URL = "https://jsonmock.hackerrank.com/api/food_outlets"


logging.basicConfig(level=logging.DEBUG)

AvgRating = Annotated[PositiveFloat, Field(ge=0.0, le=5.0)]
PositiveIntOrZero = Annotated[int, Field(ge=0)]


# Modeling data in Pydantic offers robust data validation, and the convenience of working
# with objects, for a modest performance penalty.
class RestaurantData(BaseModel):
    """Restaurant data model."""

    city: str
    estimated_cost: PositiveInt
    id: PositiveInt
    name: str
    average_rating: AvgRating
    votes: PositiveIntOrZero


class APIResponse(BaseModel):
    """Raw API response model."""

    data: list[RestaurantData]
    page: PositiveInt
    per_page: PositiveIntOrZero
    total: PositiveIntOrZero
    total_pages: PositiveInt


class NoDataError(Exception):
    """Raised when API returns an empty data key."""


def retry_api_call(exception: Exception) -> bool:
    """Whether to retry an API call based on the exception raised.

    Passed to the retrying.retry() decorator of the API call function
    to determine which exceptions should be retried.

    Returns True for any network, client, or server errors that might be transient.

    Reference: https://www.python-httpx.org/exceptions/
    """
    # These are the only network errors we care to retry.
    transient_network_errors = (httpx.ConnectError, httpx.ReadError, httpx.WriteError)
    # Any of these server errors are potentially transient, and worth retrying.
    transient_server_errors = (
        httpx.codes.INTERNAL_SERVER_ERROR,
        httpx.codes.BAD_GATEWAY,
        httpx.codes.GATEWAY_TIMEOUT,
        httpx.codes.SERVICE_UNAVAILABLE,
    )
    is_transient_network_error = isinstance(exception, transient_network_errors)
    is_transient_server_error = False
    is_rate_limited = False
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        if status_code == httpx.codes.TOO_MANY_REQUESTS:
            # The 429 Too Many Requests response should also come with a
            # Retry-After header, indicating when the next request should be
            # made. For production it would be better to respect this header,
            # but for most cases an exponential backoff is fine.
            is_rate_limited = True
        if status_code in transient_server_errors:
            is_transient_network_error = True

    return is_rate_limited or is_transient_server_error or is_transient_network_error


# Exponential backoff for failures, up to three attempts.
@retry(
    wait_exponential_multiplier=1000,
    stop_max_attempt_number=3,
    retry_on_exception=retry_api_call,
)
async def api_call(
    client: httpx.AsyncClient, city: str, page: PositiveInt = 1
) -> APIResponse:
    """Make an API call for a single page of data for a given city.

    Args:
        client: Open instance of httpx.AsyncClient.
        city: Name of the city to retrieve restaurant data for.
        page: Page of data to retrieve. Defaults to 1.

    Returns:
        An APIResponse model based on to the data structure returned by the API.

    Raises:
        - httpx.HTTPStatusError if status code is 4xx or 5xx.
        - NoDataError if no data found in the response.

    """
    params = {"city": city, "page": page}
    response = await client.get(url=BASE_URL, params=params)
    try:
        response.raise_for_status()
    except httpx.CloseError:
        # We don't care if the connection couldn't be closed gracefully.
        # TODO: Log this.
        pass

    # orjson is faster and more correct than the stdlib json module.
    # https://github.com/ijl/orjson
    json = orjson.loads(response.content)
    if not json["data"]:
        raise NoDataError(f'No restaurant data found for city "{city}"')

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


async def get_highest_rated_restaurants(city: str, limit: PositiveInt = 5) -> list[str]:
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
    data.sort(key=lambda m: m.average_rating, reverse=True)
    highest_rating = data[0].average_rating
    return [x.name for x in data if x.average_rating == highest_rating][:limit]


if __name__ == "__main__":
    # UVloop is a fast, drop-in replacement for the default event loop. Performance
    # is comparable to golang.
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    start_time = time.perf_counter()
    results = asyncio.run(get_highest_rated_restaurants(city=CITY))
    end_time = time.perf_counter()
    running_time = end_time - start_time
    pprint.pprint(results)
    print(f"Running time: {running_time:4f}s")
