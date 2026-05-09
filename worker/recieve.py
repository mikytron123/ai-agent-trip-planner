import datetime
import io
import os
import sys
from unittest.mock import Mock

import boto3
import msgspec
import pika
import psycopg
import sys
import os
from pathlib import Path
from botocore.client import Config
from botocore.exceptions import ClientError
from crewai import LLM, Agent, Crew, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from phoenix.otel import register
from types_boto3_s3.client import S3Client
if str(Path(__file__).parent) not in sys.path:
    sys.path.append(str(Path(__file__).parent))
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.append(str(Path(__file__).parent.parent))

from appconfig import config
from tools import AttractionTool, WeatherTool

USE_MOCK = config.use_mock
POSTGRES_HOST = config.postgres_host
POSTGRES_USER = config.postgres_user
POSTGRES_PASS = config.postgres_pass
POSTGRES_DB = config.postgres_db
POSTGRES_PORT = config.postgres_port

RABBITMQ_USER = config.rabbitmq_user
RABBITMQ_PASS = config.rabbitmq_pass
RABBITMQ_HOST = config.rabbitmq_host
RABBITMQ_PORT = config.rabbitmq_port
RABBITMQ_QUEUE = config.rabbitmq_queue

RUSTFS_HOST = config.rustfs_host
RUSTFS_PORT = config.rustfs_port
RUSTFS_ACCESS_KEY = config.rustfs_access_key
RUSTFS_SECRET_KEY = config.rustfs_secret_key
RUSTFS_BUCKET = config.rustfs_bucket

OLLAMA_HOST = config.ollama_host
OLLAMA_PORT = config.ollama_port
OLLAMA_LLM = config.ollama_llm
PHOENIX_COLLECTOR_ENDPOINT = config.phoenix_collector_endpoint

# tracer_provider = register(
#     endpoint=PHOENIX_COLLECTOR_ENDPOINT,
#     project_name="crewai-tracing",
#     auto_instrument=True,
#     protocol="http/protobuf",
#     batch=True,
# )


@CrewBase
class MultiAgentCrew:
    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/task.yaml"

    @agent
    def weather_agent(self) -> Agent:
        llm = LLM(
            provider="ollama",
            model=f"{OLLAMA_LLM}",
            base_url=f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/v1/",
            api_key="ollama",
            timeout=120,
            temperature=0.1,
        )
        return Agent(
            config=self.agents_config["weather"],  # type: ignore[index]
            llm=llm,
            allow_delegation=True,
            max_iter=5,
        )

    @agent
    def attractions_agent(self) -> Agent:
        llm = LLM(
            provider="ollama",
            model=f"{OLLAMA_LLM}",
            base_url=f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/v1/",
            api_key="ollama",
            timeout=120,
            temperature=0.1,
        )
        return Agent(
            config=self.agents_config["trip"],  # type: ignore[index]
            llm=llm,
            allow_delegation=True,
            max_iter=5,
        )

    @task
    def weather_task(self) -> Task:
        return Task(
            config=self.tasks_config["weather_task"],  # type: ignore[index]
            agent=self.weather_agent(),
            tools=[WeatherTool()],
        )

    @task
    def attraction_task(self) -> Task:
        return Task(
            config=self.tasks_config["attraction_task"],  # type: ignore[index]
            agent=self.attractions_agent(),
            tools=[AttractionTool()],
            context=[self.weather_task()],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, verbose=True)


class Payload(msgspec.Struct):
    task_id: str
    city: str
    start_date: str
    end_date: str


def create_crew_yaml(mock: bool) -> Crew:

    if mock:
        crew_mock = Mock()
        output_mock = Mock()
        crew_mock.kickoff.return_value = output_mock
        output_mock.raw = "test"
        return crew_mock

    else:
        return MultiAgentCrew().crew()


def update_db(id: str, state: str):
    """Updates database with given state at task id

    Args:
        id (str): id string for the task
        state (str): state to update
    """
    with psycopg.connect(
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASS}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    ) as conn, conn.cursor() as cursor:
        data = {
            "state": state,
            "updated_at": datetime.datetime.now(),
            "task_id": id,
        }
        cursor.execute(
            """Update tasks set state = %(state)s, updated_at = %(updated_at)s  where id = %(task_id)s""",
            data,
        )
        conn.commit()


def bucket_exists(s3_client: S3Client, bucket_name: str):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' exists.")
        return True
    except ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code == 404:
            print(f"Bucket '{bucket_name}' does not exist.")
        elif error_code == 403:
            print(f"Access to bucket '{bucket_name}' is forbidden.")
        else:
            print(f"An error occurred: {e}")
        return False


def upload_text_to_rustfs(client: S3Client, bucket: str, key: str, text_content: str):
    """
    Connects to RustFS, ensures a bucket exists, and uploads text content as an object.

    Args:
        client (s3client): boto3 client
        bucket (str): Name of the bucket to upload to.
        key (str): Name of the object (file) in the bucket.
        text_content (str): The string content to upload.
    """
    # --- 1. Ensure Bucket Exists ---
    try:
        found = bucket_exists(client, bucket)
        if not found:
            client.create_bucket(Bucket=bucket)
            print(f"Bucket '{bucket}' created successfully.")
        else:
            print(f"Bucket '{bucket}' already exists.")
    except Exception as e:
        print(f"An unexpected error occurred during bucket handling: {e}")
        return

    # --- 2. Prepare Data for Upload ---
    # Convert the string content to bytes and get its length.
    # put_object requires a file-like object (stream) and the data length.
    try:
        text_bytes = text_content.encode("utf-8")
        text_stream = io.BytesIO(text_bytes)
    except Exception as e:
        print(f"Error preparing data for upload: {e}")
        return

    # --- 3. Upload the Object ---
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=text_stream,
            ContentType="text/plain",  # Set the content type explicitly
        )
        print(f"Successfully uploaded '{key}' to bucket '{bucket}'. ")
    except Exception as e:
        print(f"An unexpected error occurred during upload: {e}")


def main():
    creds = pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASS)
    connection_params = pika.ConnectionParameters(
        host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=creds
    )
    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()

    channel.queue_declare(queue=RABBITMQ_QUEUE)
    decoder = msgspec.msgpack.Decoder(type=Payload)

    def callback(ch, method, properties, body):
        print(f" [x] Received {body}")

        data_decoded = decoder.decode(body)

        task_id = data_decoded.task_id
        city = data_decoded.city
        start_date = data_decoded.start_date
        end_date = data_decoded.end_date

        update_db(task_id, "running")

        crew = create_crew_yaml(USE_MOCK)
        output = crew.kickoff(
            inputs={"city": city, "start_date": start_date, "end_date": end_date}
        )

        RUSTFS_ENDPOINT = f"http://{RUSTFS_HOST}:{RUSTFS_PORT}"
        # --- Bucket and File Details ---
        client = boto3.client(
            "s3",
            endpoint_url=RUSTFS_ENDPOINT,
            aws_access_key_id=RUSTFS_ACCESS_KEY,
            aws_secret_access_key=RUSTFS_SECRET_KEY,
            config=Config(signature_version="s3v4"),
        )

        upload_text_to_rustfs(client, RUSTFS_BUCKET, f"{task_id}.txt", output.raw)
        print(" [x] finished processing")
        update_db(task_id, "done")

    channel.basic_consume(
        queue=RABBITMQ_QUEUE, on_message_callback=callback, auto_ack=True
    )

    print(" [*] Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
