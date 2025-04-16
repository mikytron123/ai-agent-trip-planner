from fastapi import FastAPI
from pydantic import BaseModel
from crewai import Agent, LLM, Task, Crew
from tools import WeatherTool, AttractionTool
import dotenv

dotenv.load_dotenv()


class TripDetails(BaseModel):
    city: str
    start_date: str
    end_date: str


class AgentOuput(BaseModel):
    output: str


app = FastAPI()


@app.post("/agents/invoke")
def invoke_agent(data: TripDetails) -> AgentOuput:
    city = data.city
    start_date = data.start_date
    end_date = data.end_date

    weather_agent = Agent(
        role="Weather Forecaster",
        goal="Getting weather details for a {city} between {start_date} and {end_date}",
        backstory="You are an expert weather forecaster for {city}",
        llm=LLM(
            model="ollama/granite3.2:8b", base_url="http://localhost:11434", timeout=120
        ),
        allow_delegation=True,
    )

    attraction_agent = Agent(
        role="Trip Planner",
        goal="Find attractions for a {city}",
        backstory="You are an expert trip planner for {city}",
        llm=LLM(
            model="ollama/granite3.2:8b", base_url="http://localhost:11434", timeout=120
        ),
    )

    weather_task = Task(
        description="Get historical weather information between {start_date} and {end_date} for {city}",
        expected_output="A summary of the weather conditions for the given time period",
        agent=weather_agent,
        tools=[WeatherTool()],
    )

    attraction_task = Task(
        description="Get top attractions for {city}",
        expected_output="A bullet point summary of attractions to visit based on the weather condtions such as rain."
        " Show museums or religion attractions when there is rain and architecture or natural attractions when there is no rain."
        " If there are no attractions for a specific category, move to a different category",
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
    return AgentOuput(output=output.raw)
