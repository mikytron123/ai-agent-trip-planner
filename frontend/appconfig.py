import environ
from dotenv import load_dotenv


@environ.config(prefix="")
class AppConfig:
    server_host: str = environ.var(default="localhost")
    server_port: str = environ.var(default="8000")


load_dotenv()
config = environ.to_config(AppConfig)
