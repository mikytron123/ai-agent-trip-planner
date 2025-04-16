from dotenv import load_dotenv
from shiny import App, Inputs, Outputs, Session, reactive, ui, render
import datetime
import httpx

# Define UI
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_text(id="city", label="city", placeholder="Select a city",value="Toronto"),
        ui.input_date_range(
            id="date_range", label="date range", max=datetime.date.today(),start="2024-02-01",end="2024-02-02"
        ),
        ui.input_action_button("plan", "Plan a trip", class_="btn-primary"),
    ),
    ui.output_ui(
        "response",
    ),
    title="AI Trip Planner",
)


# Define server
def server(input: Inputs, output: Outputs, session: Session):
    _ = load_dotenv()

    @render.ui
    @reactive.event(input.plan)
    def response():
        city = input.city()
        start_date, end_date = input.date_range()
        params = {"city":city,"start_date":str(start_date),"end_date":str(end_date)}
        resp = httpx.post("http://localhost:8000/agents/invoke",json=params,timeout=240).json()
        print(resp)
        completion = resp["output"]
        return ui.markdown(completion)


# Create the Shiny app
app = App(app_ui, server)
