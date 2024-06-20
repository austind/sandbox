import asyncio
import logging
import pprint
import time
from functools import wraps
from typing import Annotated, Iterable

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

# Potentially transient server errors to include in retry attempts
TRANSIENT_SERVER_ERRORS = (
    httpx.codes.INTERNAL_SERVER_ERROR,
    httpx.codes.BAD_GATEWAY,
    httpx.codes.GATEWAY_TIMEOUT,
    httpx.codes.SERVICE_UNAVAILABLE,
)
TRANSIENT_NETWORK_ERRORS = (httpx.ConnectError, httpx.ReadError, httpx.WriteError)

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


class MaxAttemptsFailed(Exception):
    """Raised when maximum attempts to make an API call fail."""


def retry_transient_errors(
    max_attempts: int = 3,
    exponential_backoff_factor: float = 0.3,
    status_codes: Iterable | None = None,
    logger=None,
):
    """Retries HTTPX requests that raise potentially transient network or HTTP status errors.

    Retries the following errors up to max_attempts:
        - httpx.ConnectError
        - httpx.ReadError
        - httpx.WriteError
        - httpx.HTTPStatusError, if status_code is included in status_codes (see defaults below).

    Args:
        max_attempts: Maximum number of attempts before giving up.
        exponential_backoff_factor: Factor to multiply for exponential backoff between retries.
        status_codes: Iterable of HTTP status codes to retry in case of failure. If omitted, defaults to:
            - 429 Too Many Requests (server-side rate limiting)
            - 500 Internal Server Error
            - 502 Bad Gateway
            - 503 Service Unavailable
            - 504 Gateway Timeout
        logger: Logger instance to use. Defaults to logging.getLogger(__main__).

    Returns:
        Decorator.

    Raises:
        - httpx.ConnectError, httpx.ReadError, httpx.WriteError, or httpx.HTTPStatusError
            received on final attempt.
        - All other exceptions raised immediately.

    """
    if status_codes is None:
        status_codes = (
            httpx.codes.TOO_MANY_REQUESTS,
            httpx.codes.INTERNAL_SERVER_ERROR,
            httpx.codes.BAD_GATEWAY,
            httpx.codes.GATEWAY_TIMEOUT,
            httpx.codes.SERVICE_UNAVAILABLE,
        )

    if logger is None:
        import logging

        logger = logging.getLogger(__name__)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                delay = exponential_backoff_factor * (2**attempt)
                last_exception = None
                try:
                    return await func(*args, **kwargs)
                except httpx.ConnectError as exc:
                    logger.warn(
                        f"Network error connecting to host: {exc.request.url.host}"
                    )
                    last_exception = exc
                except httpx.ReadError as exc:
                    logger.warn(f"Network error reading data: {exc.request.url}")
                    last_exception = exc
                except httpx.WriteError as exc:
                    logger.warn(f"Network error writing data: {exc.request.url}")
                    last_exception = exc
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    if status_code in status_codes:
                        last_exception = exc
                        if attempt < max_attempts:
                            if status_code == httpx.codes.TOO_MANY_REQUESTS:
                                retry_after = float(
                                    exc.response.headers.get("Retry-After", delay)
                                )
                                logger.warn(
                                    f"Rate limited: {exc.request.url}, retrying after {retry_after}s..."
                                )
                                await asyncio.sleep(retry_after)
                            else:
                                logger.warn(
                                    f"HTTP error {status_code}: {exc.request.url}, retrying..."
                                )
                    else:
                        raise
                if attempt < max_attempts:
                    logger.info(f"Waiting {delay}s before next attempt...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {max_attempts} attempts failed.")
            raise (
                last_exception
                if last_exception
                else MaxAttemptsFailed(f"Failed after {max_attempts} attempts.")
            )

        return wrapper

    return decorator


@retry_transient_errors(max_attempts=3, exponential_backoff_factor=1.0)
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
