import asyncio
import logging
import pprint
import time
from typing import Annotated

import httpx
import orjson
import uvloop
from pydantic import BaseModel, Field, PositiveFloat, PositiveInt
from tenacity import (RetryCallState, retry, retry_if_exception,
                      stop_after_attempt, wait_exponential)

"""Return a list of top-rated restaurants in a given city.

Return a list of up to five restaurant names for a given city, which all 
have the highest average rating. For example, if a city's highest-rated
restaurant has an average rating of 4.7 stars, return only up to five
total restaurants that also have 4.7 stars.
"""

CITY = "denver"
BASE_URL = "https://jsonmock.hackerrank.com/api/food_outlets"

# Potentially transient HTTP errors to include in retry attempts
POTENTIALLY_TRANSIENT_HTTP_ERRORS = (
    httpx.codes.TOO_MANY_REQUESTS,
    httpx.codes.INTERNAL_SERVER_ERROR,
    httpx.codes.BAD_GATEWAY,
    httpx.codes.GATEWAY_TIMEOUT,
    httpx.codes.SERVICE_UNAVAILABLE,
)
POTENTIALLY_TRANSIENT_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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


def is_potentially_transient_error(exc) -> bool:
    """Whether an exception is a potentially transient error.

    Args:
        exc: Exception to consider.

    Returns:
        Boolean if exception is potentially transient.

    Raises:
        N/A

    """
    if isinstance(exc, POTENTIALLY_TRANSIENT_NETWORK_ERRORS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in POTENTIALLY_TRANSIENT_HTTP_ERRORS
    return False


def context_aware_backoff(retry_state: RetryCallState) -> float:
    """Use Retry-After header value for HTTP 429, exponential backoff otherwise.

    Args:
        retry_state: A tenacity.RetryCallState.

    Returns:
        A float for how long to wait between retries.

    Raises:
        N/A

    """
    last_exception = retry_state.outcome.exception()
    if (
        isinstance(last_exception, httpx.HTTPStatusError)
        and last_exception.response.status_code == httpx.codes.TOO_MANY_REQUESTS
    ):
        return float(last_exception.response.headers.get("Retry-After", 1.0))
    return wait_exponential(multiplier=1, min=1, max=10)(retry_state=retry_state)


@retry(
    stop=stop_after_attempt(3),
    wait=context_aware_backoff,
    retry=retry_if_exception(is_potentially_transient_error),
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
    except httpx.CloseError as exc:
        # If the connection wasn't closed gracefully, no need to retry.
        logger.warn(f"Error closing connection: {exc.request.url}")

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
