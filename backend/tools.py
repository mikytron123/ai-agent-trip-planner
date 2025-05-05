from functools import lru_cache
import httpx

import msgspec

from appconfig import config


API_KEY = config.api_key


class Result(msgspec.Struct):
    name: str
    latitude: float
    longitude: float
    country_code: str
    country: str


class GeocodingSearchResponse(msgspec.Struct):
    results: list[Result]


@lru_cache
def get_coordinates(city: str) -> tuple[float, float]:
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
    geocoding_params = {"name": city, "count": 1, "language": "en", "format": "json"}
    resp = httpx.get(url=geocoding_url, params=geocoding_params)
    if resp.status_code < 200 or resp.status_code > 200:
        raise ValueError(
            f"Non 200 status code {resp.status_code}, {resp.content.decode()}"
        )
    decoder = msgspec.json.Decoder(type=GeocodingSearchResponse)

    try:
        geocoding_response = decoder.decode(resp.content)
    except Exception:
        raise ValueError("City is not found")

    if geocoding_response.results[0].name != city:
        raise ValueError("City is not found")

    latitude = geocoding_response.results[0].latitude
    longitude = geocoding_response.results[0].longitude

    return latitude, longitude
