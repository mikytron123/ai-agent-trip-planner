from dotenv import load_dotenv
import environ


@environ.config(prefix="")
class AppConfig:
    ollama_host = environ.var(default="localhost")
    ollama_port = environ.var(default="11434")
    ollama_llm = environ.var(default="granite3.2:8b")
    api_key = environ.var()

load_dotenv()
config = environ.to_config(AppConfig)
