import asyncio
import time

import httpx
import uvloop


async def fetch_url(client, url):
    response = await client.get(url)
    return response


async def fetch_all_urls(urls):
    async with httpx.AsyncClient(http2=True) as client:
        tasks = [fetch_url(client, url) for url in urls]
        responses = await asyncio.gather(*tasks)
        return responses


urls = ["https://example.com", "https://example.org", "https://example.net"]


async def main():
    responses = await fetch_all_urls(urls)
    for response in responses:
        print(f"URL: {response.url} - Status Code: {response.status_code}")


def measure_execution_time(loop_policy):
    asyncio.set_event_loop_policy(loop_policy)
    start_time = time.perf_counter()
    asyncio.run(main())
    end_time = time.perf_counter()
    return end_time - start_time


if __name__ == "__main__":
    # Measure execution time without uvloop
    time_without_uvloop = measure_execution_time(asyncio.DefaultEventLoopPolicy())
    print(f"Execution time without uvloop: {time_without_uvloop:.4f} seconds")

    # Measure execution time with uvloop
    time_with_uvloop = measure_execution_time(uvloop.EventLoopPolicy())
    print(f"Execution time with uvloop: {time_with_uvloop:.4f} seconds")
