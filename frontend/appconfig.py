import environ
from dotenv import load_dotenv

@environ.config(prefix="")
class AppConfig:
    server_host = environ.var(default="localhost")
    server_port = environ.var(default="8000")

load_dotenv()
config = environ.to_config(AppConfig)
