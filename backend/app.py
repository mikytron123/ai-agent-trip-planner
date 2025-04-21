from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from crewai import Agent, LLM, Task, Crew
from tools import WeatherTool, AttractionTool, get_coordinates
from appconfig import config
import pandas as pd
import time

OLLAMA_HOST = config.ollama_host
OLLAMA_PORT = config.ollama_port
OLLAMA_LLM = config.ollama_llm


class TripDetails(BaseModel):
    city: str
    start_date: str
    end_date: str


class AgentOuput(BaseModel):
    output: str


app = FastAPI()


@app.post("/agents/invoke")
def invoke_agent(data: TripDetails) -> AgentOuput:
    start_time = time.perf_counter()
    city = data.city
    start_date = data.start_date
    end_date = data.end_date

    if pd.to_datetime(start_date) >= pd.to_datetime(end_date):
        raise HTTPException(
            status_code=400, detail="Start date must be before end date"
        )

    try:
        _ = get_coordinates(city=city)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    llm = LLM(
        model=f"ollama/{OLLAMA_LLM}",
        base_url=f"http://{OLLAMA_HOST}:{OLLAMA_PORT}",
        timeout=120,
    )
    weather_agent = Agent(
        role="Weather Forecaster",
        goal="Getting weather details for a {city} between {start_date} and {end_date}",
        backstory="You are an expert weather forecaster for {city}",
        llm=llm,
        allow_delegation=True,
        max_iter=5,
    )

    attraction_agent = Agent(
        role="Trip Planner",
        goal="Find attractions for a {city}",
        backstory="You are an expert trip planner for {city}",
        llm=llm,
        max_iter=5,
    )

    weather_task = Task(
        description="Get historical weather information such as the temperature, amount of rain, amount of precipation and precipation hours between {start_date} and {end_date} for {city}",
        expected_output="A summary of the weather information for the given time period.",
        agent=weather_agent,
        tools=[WeatherTool()],
    )

    attraction_task = Task(
        description="Get information about attractions for {city}."
        " Show museums or religion attractions when there is rain."
        " Show architecture or natural attractions when there is no rain."
        "If there are no attractions for a specific category, move to a different category",
        expected_output="A bullet point summary of attractions to visit based on the weather condtions such as rain."
        " "
        " ",
        agent=attraction_agent,
        tools=[AttractionTool()],
        context=[weather_task],
    )

    crew = Crew(
        agents=[weather_agent, attraction_agent],
        tasks=[weather_task, attraction_task],
        verbose=True,
    )

    output = crew.kickoff(
        inputs={"city": city, "start_date": start_date, "end_date": end_date}
    )
    end_time = time.perf_counter()
    print(
        f"It took {end_time - start_time} seconds to run the api for {city}, {start_date}, {end_date}"
    )
    return AgentOuput(output=output.raw)
