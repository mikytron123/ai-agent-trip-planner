import environ
from dotenv import load_dotenv

def use_mock_converter(x):
    if isinstance(x,bool):
        return x
    elif isinstance(x,str):
        return x.casefold()=="true".casefold()

@environ.config(prefix="")
class AppConfig:
    postgres_host: str = environ.var(default="localhost")
    postgres_user: str = environ.var(default="postgres")
    postgres_db: str = environ.var(default="postgres")
    postgres_pass: str = environ.var(default="postgres")
    postgres_port: str = environ.var(default="5433")
    rabbitmq_user: str = environ.var(default="user")
    rabbitmq_pass: str = environ.var(default="password")
    rabbitmq_host: str = environ.var(default="localhost")
    rabbitmq_port: int = environ.var(default=5672, converter=int)
    rabbitmq_queue: str = environ.var(default="messages")
    rustfs_host: str = environ.var(default="localhost")
    rustfs_port: str = environ.var(default="9000")
    rustfs_access_key: str = environ.var(default="rustfsadmin")
    rustfs_secret_key: str = environ.var(default="rustfsadmin")
    rustfs_bucket: str = environ.var(default="llm")
    api_key: str = environ.var(default="")
    use_mock: bool = environ.var(
        default=False, converter=use_mock_converter
    )
    ollama_host: str = environ.var(default="localhost")
    ollama_port: str = environ.var(default="11434")
    ollama_llm: str = environ.var(default="qwen3:8b")
    phoenix_collector_endpoint: str = environ.var(
        default="http://localhost:6006/v1/traces"
    )


load_dotenv()
config = environ.to_config(AppConfig)
