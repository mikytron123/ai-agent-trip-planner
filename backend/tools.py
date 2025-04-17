from functools import lru_cache
import httpx
from pydantic import BaseModel, Field
from typing import Literal, Type
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
from crewai.tools import BaseTool
import os
from dotenv import load_dotenv
from dataclasses import dataclass

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
    if resp.status_code<200 or resp.status_code>200:
        raise ValueError(f"Non 200 status code {resp.status_code}, {resp.content}")
    decoder = msgspec.json.Decoder(type=GeocodingSearchResponse)
    print(resp.content)
    
    try:
        geocoding_response = decoder.decode(resp.content)
    except Exception as e:
        raise ValueError("City is not found")
    
    if geocoding_response.results[0].name != city:
        raise ValueError("City is not found")

    latitude = geocoding_response.results[0].latitude
    longitude = geocoding_response.results[0].longitude

    return latitude, longitude


class WeatherToolSchema(BaseModel):
    city: str = Field(..., description="name of a city")
    start_date: str = Field(..., description="A date formated as year-month-day")
    end_date: str = Field(..., description="A date formated as year-month-day")


class WeatherTool(BaseTool):
    name: str = "weather tool"
    description: str = (
        "Useful for getting daily weather for a city between a start_date and end_date"
    )
    args_schema: Type[BaseModel] = WeatherToolSchema

    def _run(self, city: str, start_date: str, end_date: str) -> dict:
        latitude, longitude = get_coordinates(city)

        # Setup the Open-Meteo API client with cache and retry on error
        cache_session = requests_cache.CachedSession(".cache", expire_after=-1)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)

        # Make sure all required weather variables are listed here
        # The order of variables in hourly or daily is important to assign them correctly below
        url = "https://archive-api.open-meteo.com/v1/archive"

        daily_vars = [
            "temperature_2m_mean",
            "rain_sum",
            "precipitation_sum",
            "precipitation_hours",
        ]

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "daily": daily_vars,
        }
        responses = openmeteo.weather_api(url, params=params)

        # Process first location. Add a for-loop for multiple locations or weather models
        response = responses[0]

        # Process daily data. The order of variables needs to be the same as requested.
        daily = response.Daily()
        if daily is None:
            raise ValueError("response is empty")
        df_data = {}
        for i, v in enumerate(daily_vars):
            df_data[v] = daily.Variables(i).ValuesAsNumpy()  # type: ignore
        dates = pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left",
        ).to_list()
        df_data["date"] = dates

        return df_data


class AttractionToolSchema(BaseModel):
    city: str = Field(..., description="name of a city")
    kinds: (
        Literal["museums"]
        | Literal["religion"]
        | Literal["architecture"]
        | Literal["natural"]
    ) = Field(
        ...,
        description="category of attractions. This must be museums, religion, architecture, or natural",
    )


class AttractionTool(BaseTool):
    name: str = "Attractions Tool"
    description: str = "Useful for getting attractions for a city"
    args_schema: Type[BaseModel] = AttractionToolSchema

    def _run(self, city: str, kinds: str) -> dict:
        latitude, longitude = get_coordinates(city)
        trip_url = "https://api.opentripmap.com/0.1/en/places/radius"
        params = {
            "lang": "en",
            "radius": 5000,
            "lon": longitude,
            "lat": latitude,
            "format": "json",
            "limit": 5,
            "kinds": kinds,
            "apikey": API_KEY,
        }

        resp = httpx.get(url=trip_url, params=params).json()
        return resp
