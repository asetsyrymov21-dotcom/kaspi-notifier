import requests
from dotenv import load_dotenv
import os

load_dotenv()

url = (
    "https://kaspi.kz/shop/api/v2/orders"
    "?filter[orders][creationDate][$ge]=1773410329761"
    "&page[number]=0"
    "&page[size]=10"
)

headers = {
    "X-Auth-Token": os.environ["KASPI_API_KEY"],
    "Accept": "application/vnd.api+json",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "User-Agent": "PostmanRuntime/7.52.0",
}

resp = requests.get(url, headers=headers, timeout=(10, 20))
print("status:", resp.status_code)
print("url:", resp.url)
print(resp.text[:3000])
