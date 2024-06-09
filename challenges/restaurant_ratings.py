import asyncio
import pprint
import logging

import httpx

"""Return a list of top-rated restaurants in a given city.

Return a list of up to five restaurant names for a given city, which all 
have the highest average rating. For example, if a city's highest-rated
restaurant has an average rating of 4.7 stars, return only up to five
total restaurants that also have 4.7 stars.
"""

CITY = "denver"
BASE_URL = "https://jsonmock.hackerrank.com/api/food_outlets"


logging.basicConfig(handlers=[logging.StreamHandler()], level=logging.DEBUG)


async def api_call(city: str, page: int = 1) -> dict:
    """Make an API call to retrieve a single page of data for a given city.

    Args:
        city: Name of the city to retrieve restaurant data for.
        page: Page of data to retrieve. Defaults to 1.

    Returns:
        An unmodified dict of API results.

    Raises:
        - httpx.HTTPError if status code is not 2XX
        - ValueError if no data found in the response.

    """
    url = f"{BASE_URL}?city={city}&page={page}"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if not data["data"]:
        raise ValueError(f'No restaurant data found for city "{city}"')
    return data


async def get_restaurant_data(city: str) -> list[dict]:
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
    data: dict = await api_call(city=city)
    if data["total_pages"] > 1:
        coros = [
            api_call(city=city, page=page) for page in range(2, data["total_pages"] + 1)
        ]
        page_data = await asyncio.gather(*coros)
        for page in page_data:
            data["data"].extend(page["data"])
    return data["data"]


async def get_highest_rated_restaurants(city: str, limit: int = 5) -> list[str]:
    """Get the N restaurants in a given city that all share the same highest rating.

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
    sorted_data = sorted(
        data, key=lambda d: d["user_rating"]["average_rating"], reverse=True
    )
    highest_rating = sorted_data[0]["user_rating"]["average_rating"]
    return [
        x["name"]
        for x in sorted_data
        if x["user_rating"]["average_rating"] == highest_rating
    ][:limit]


if __name__ == "__main__":
    client = httpx.AsyncClient()
    results = asyncio.run(get_highest_rated_restaurants(city=CITY))
    pprint.pprint(results)
