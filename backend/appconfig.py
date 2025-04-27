from dotenv import load_dotenv
import environ


@environ.config(prefix="")
class AppConfig:
    ollama_host: str = environ.var(default="localhost")
    ollama_port: str = environ.var(default="11434")
    ollama_llm: str = environ.var(default="granite3.2:8b")
    api_key: str = environ.var()
    phoenix_collector_endpoint: str = environ.var(
        default="http://localhost:6006/v1/traces"
    )
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
    minio_host: str = environ.var(default="localhost")
    minio_port: str = environ.var(default="9092")
    minio_access_key: str = environ.var(default="minio")
    minio_secret_key: str = environ.var(default="miniopass")
    minio_bucket: str = environ.var(default="llm")


load_dotenv()
config = environ.to_config(AppConfig)
