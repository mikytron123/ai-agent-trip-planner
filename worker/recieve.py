from typing import TypedDict
import pika
import sys
import os
import msgpack
import psycopg
import io
from minio import Minio
from minio.error import S3Error
from appconfig import config
from crewai import Agent, LLM, Task, Crew
from crewai.project import CrewBase, agent, task, crew
from crewai.agents.agent_builder.base_agent import BaseAgent
from tools import WeatherTool, AttractionTool
from pydantic import TypeAdapter, ValidationError
from phoenix.otel import register
import datetime

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

MINIO_HOST = config.minio_host
MINIO_PORT = config.minio_port
MINIO_ACCESS_KEY = config.minio_access_key
MINIO_SECRET_KEY = config.minio_secret_key
MINIO_BUCKET = config.minio_bucket

OLLAMA_HOST = config.ollama_host
OLLAMA_PORT = config.ollama_port
OLLAMA_LLM = config.ollama_llm
PHOENIX_COLLECTOR_ENDPOINT = config.phoenix_collector_endpoint

tracer_provider = register(
    endpoint=PHOENIX_COLLECTOR_ENDPOINT,
    project_name="crewai-tracing",
    auto_instrument=True,
    protocol="http/protobuf",
    batch=True,
)

class Payload(TypedDict):
    task_id:str
    city: str
    start_date: str
    end_date:str

def create_crew_yaml() -> Crew:
    @CrewBase
    class MultiAgentCrew:
        agents: list[BaseAgent]
        tasks: list[Task]

        agents_config = "config/agents.yaml"
        tasks_config = "config/task.yaml"

        llm = LLM(
            model=f"ollama/{OLLAMA_LLM}",
            base_url=f"http://{OLLAMA_HOST}:{OLLAMA_PORT}",
            timeout=120,
            temperature=0.1,
        )

        @agent
        def weather_agent(self) -> Agent:
            return Agent(
                config=self.agents_config["weather"],  # type: ignore[index]
                llm=self.llm,
                allow_delegation=True,
                max_iter=5,
            )

        @agent
        def attractions_agent(self) -> Agent:
            return Agent(
                config=self.agents_config["trip"],  # type: ignore[index]
                llm=self.llm,
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

    return MultiAgentCrew().crew()


def update_db(id: str, state: str):
    """Updates database with given state at task id

    Args:
        id (str): id string for the task
        state (str): state to update
    """
    with psycopg.connect(
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASS}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    ) as conn:
        with conn.cursor() as cursor:
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


def upload_text_to_minio(
    client: Minio, bucket_name: str, object_name: str, text_content: str
):
    """
    Connects to MinIO, ensures a bucket exists, and uploads text content as an object.

    Args:
        client (Minior): Minio client
        bucket_name (str): Name of the bucket to upload to.
        object_name (str): Name of the object (file) in the bucket.
        text_content (str): The string content to upload.
    """
    # --- 1. Ensure Bucket Exists ---
    try:
        found = client.bucket_exists(bucket_name)
        if not found:
            client.make_bucket(bucket_name)
            print(f"Bucket '{bucket_name}' created successfully.")
        else:
            print(f"Bucket '{bucket_name}' already exists.")
    except S3Error as e:
        print(f"Error checking or creating bucket '{bucket_name}': {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred during bucket handling: {e}")
        return

    # --- 2. Prepare Data for Upload ---
    # Convert the string content to bytes and get its length.
    # put_object requires a file-like object (stream) and the data length.
    try:
        text_bytes = text_content.encode("utf-8")
        text_stream = io.BytesIO(text_bytes)
        stream_length = len(text_bytes)
    except Exception as e:
        print(f"Error preparing data for upload: {e}")
        return

    # --- 3. Upload the Object ---
    try:
        result = client.put_object(
            bucket_name,
            object_name,
            text_stream,
            length=stream_length,
            content_type="text/plain",  # Set the content type explicitly
        )
        print(
            f"Successfully uploaded '{object_name}' to bucket '{bucket_name}'. "
            f"ETag: {result.etag}, Version ID: {result.version_id}"
        )
    except S3Error as e:
        print(f"Error uploading object '{object_name}' to bucket '{bucket_name}': {e}")
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

    def callback(ch, method, properties, body):
        print(f" [x] Received {body}")
        ta = TypeAdapter(Payload)
        data_decoded = msgpack.unpackb(body)
        try:
            data_decoded = ta.validate_python(data_decoded)
        except ValidationError as e:
            print(e)
            raise(e)
        
        task_id = data_decoded["task_id"]
        city = data_decoded["city"]
        start_date = data_decoded["start_date"]
        end_date = data_decoded["end_date"]

        update_db(task_id, "running")

        crew = create_crew_yaml()
        output = crew.kickoff(
            inputs={"city": city, "start_date": start_date, "end_date": end_date}
        )

        MINIO_ENDPOINT = f"{MINIO_HOST}:{MINIO_PORT}"
        # --- Bucket and File Details ---

        client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False,
        )

        upload_text_to_minio(client, MINIO_BUCKET, f"{task_id}.txt", output.raw)
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
