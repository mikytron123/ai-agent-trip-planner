from shiny import App, Inputs, Outputs, Session, reactive, ui, render
import datetime
import httpx
from appconfig import config

SERVER_HOST = config.server_host
SERVER_PORT = config.server_port
task_id = None

def poll_func() -> str:
    if task_id is not None:
        resp = httpx.get(
            f"http://{SERVER_HOST}:{SERVER_PORT}/tasks/{task_id}/status"
        ).json()
        return resp["state"]
    return "missing"


def task_output() -> str:
    if task_id is not None:
        resp = httpx.get(f"http://{SERVER_HOST}:{SERVER_PORT}/tasks/{task_id}/output")
        if resp.status_code > 300:
            return "Error"
        else:
            return str(resp.json())
    return ""


# Define UI
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_text(
            id="city", label="city", placeholder="Select a city", value="Toronto"
        ),
        ui.input_date_range(
            id="date_range",
            label="date range",
            max=datetime.date.today(),
            start="2024-02-01",
            end="2024-02-02",
        ),
        ui.input_action_button("task", "Plan a trip", class_="btn-primary"),
    ),
    ui.output_ui(
        "response",
    ),
    title="AI Trip Planner",
)


# Define server
def server(input: Inputs, output: Outputs, session: Session):

    current_data = reactive.value(task_output())
    polling_status = reactive.value(False)
    change_detected = reactive.value(False)

    @reactive.effect
    def _():
        if polling_status.get() is False:
            return

        reactive.invalidate_later(5)

        current_state = poll_func()

        if current_state == "done":
            current_data.set(task_output())
            change_detected.set(True)
            polling_status.set(False)
        else:
            current_data.set(current_state)

    @reactive.effect
    @reactive.event(input.task)
    def res():
        global task_id
        start_date,end_date = input.date_range()
        param = {
            "city": input.city(),
            "start_date": str(start_date),
            "end_date": str(end_date),
        }
        resp = httpx.post(
            f"http://{SERVER_HOST}:{SERVER_PORT}/task/start", json=param
        ).json()
        task_id = resp["task_id"]
        polling_status.set(True)

    @render.ui
    def response():
        cur_val = current_data.get()
        if cur_val == "running":
            return ui.HTML("""<div class="spinner-border" role="status"></div>""")
        else:
            return ui.markdown(cur_val)


# Create the Shiny app
app = App(app_ui, server)
