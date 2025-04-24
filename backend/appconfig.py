from dotenv import load_dotenv
import environ


@environ.config(prefix="")
class AppConfig:
    ollama_host:str = environ.var(default="localhost")
    ollama_port:str = environ.var(default="11434")
    ollama_llm:str = environ.var(default="granite3.2:8b")
    api_key:str = environ.var()
    phoenix_collector_endpoint:str = environ.var(default="http://localhost:6006/v1/traces")

load_dotenv()
config = environ.to_config(AppConfig)
