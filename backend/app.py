from contextlib import asynccontextmanager
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException
from minio import Minio, S3Error
import msgspec
from pydantic import BaseModel
from tools import get_coordinates
from appconfig import config
import pandas as pd
import uuid
import psycopg
import pika
import datetime

OLLAMA_HOST = config.ollama_host
OLLAMA_PORT = config.ollama_port
OLLAMA_LLM = config.ollama_llm
PHOENIX_COLLECTOR_ENDPOINT = config.phoenix_collector_endpoint

POSTGRES_HOST = config.postgres_host
POSTGRES_USER = config.postgres_user
POSTGRES_PASS = config.postgres_pass
POSTGRES_DB = config.postgres_db
POSTGRES_PORT = config.postgres_port

MINIO_HOST = config.minio_host
MINIO_PORT = config.minio_port
MINIO_ACCESS_KEY = config.minio_access_key
MINIO_SECRET_KEY = config.minio_secret_key
MINIO_BUCKET = config.minio_bucket

RABBITMQ_USER = config.rabbitmq_user
RABBITMQ_PASS = config.rabbitmq_pass
RABBITMQ_HOST = config.rabbitmq_host
RABBITMQ_PORT = config.rabbitmq_port
RABBITMQ_QUEUE = config.rabbitmq_queue


class TripDetails(BaseModel):
    city: str
    start_date: str
    end_date: str


class TaskDetails(BaseModel):
    task_id: str


class AgentOuput(BaseModel):
    output: str


class DBStatus(BaseModel):
    state: str


DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASS}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

db_conn: Optional[psycopg.Connection] = None


def create_table(db_conn: psycopg.Connection):
    with db_conn.cursor() as cursor:
        cursor.execute("""Create Table IF NOT EXISTS tasks (
    id varchar(50) primary key,
    state varchar(50),
    created_at Timestamp default current_timestamp,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
        db_conn.commit()


def insert_db(db_conn: psycopg.Connection) -> Optional[str]:
    """Insert submitted job into db"""

    cursor = None

    try:
        cursor = db_conn.cursor()
        task_id = str(uuid.uuid4())
        cur_time = datetime.datetime.now()
        data = {
            "task_id": task_id,
            "state": "submitted",
            "created_at": cur_time,
            "updated_at": cur_time,
        }
        cursor.execute(
            """Insert into tasks values (%(task_id)s,%(state)s,%(created_at)s,%(updated_at)s)""",
            data,
        )
        db_conn.commit()

        return task_id
    except Exception as e:
        print(e)
    finally:
        if cursor is not None:
            cursor.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_conn
    try:
        db_conn = psycopg.connect(DATABASE_URL)

        yield

    finally:
        if db_conn is not None:
            db_conn.close()


app = FastAPI(lifespan=lifespan)


def get_db() -> psycopg.Connection:
    if db_conn is None:
        raise RuntimeError("Db connection is not available")
    return db_conn


def read_text_from_minio(client: Minio, bucket_name: str, object_name: str):
    """
    Connects to MinIO, retrieves an object, and returns its content as a string.

    Args:
        bucket_name (str): Name of the bucket containing the object.
        object_name (str): Name of the object (file) in the bucket.

    Returns:
        str: The content of the text file as a string, or None if an error occurs.
    """
    # --- 1. Initialize MinIO Client ---
    # Create a MinIO client instance.
    # Set secure=False if running locally without HTTPS.

    # --- 2. Retrieve the Object ---
    try:
        # Get the object data from MinIO
        # The response object is a stream
        response = client.get_object(bucket_name, object_name)
        print(
            f"Successfully initiated retrieval of '{object_name}' from bucket '{bucket_name}'."
        )

        # --- 3. Read and Decode the Data ---
        # Read the data from the stream and decode it from bytes to string (assuming UTF-8)
        # Using 'with' ensures the response stream is properly closed afterwards
        with response:
            file_content_bytes = response.read()
            file_content_string = file_content_bytes.decode("utf-8")
            print("Successfully read and decoded content.")
            return file_content_string

    except S3Error as e:
        # Handle MinIO-specific errors (e.g., NoSuchKey, NoSuchBucket)
        print(
            f"MinIO S3 Error retrieving object '{object_name}' from bucket '{bucket_name}': {e}"
        )
        if e.code == "NoSuchKey":
            print(
                f"Error: The object '{object_name}' does not exist in bucket '{bucket_name}'."
            )
        elif e.code == "NoSuchBucket":
            print(f"Error: The bucket '{bucket_name}' does not exist.")
        return None
    except Exception as e:
        # Handle other potential errors (e.g., network issues, decoding errors)
        print(f"An unexpected error occurred during object retrieval or reading: {e}")
        return None


@app.get("/tasks/{task_id}/output")
async def get_task_output(task_id: str):
    MINIO_ENDPOINT = f"{MINIO_HOST}:{MINIO_PORT}"

    client = Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )
    content = read_text_from_minio(client, MINIO_BUCKET, f"{task_id}.txt")
    if content is None:
        print("exception in backend")
        raise HTTPException(status_code=400, detail="cant find obj")
    return content


@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str, db_conn: psycopg.Connection = Depends(get_db)):
    cursor = db_conn.cursor()
    data = {"id": task_id}
    cursor.execute("SELECT state from tasks where id = %(id)s", data)
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail="State not found for given task id")

    state = row[0]
    cursor.close()

    return DBStatus(state=state)


@app.post("/task/start", status_code=202)
async def start_task(data: TripDetails, db_conn: psycopg.Connection = Depends(get_db)):
    data_dict = data.model_dump()
    city = data.city
    start_date = data.start_date
    end_date = data.end_date

    if pd.to_datetime(start_date) >= pd.to_datetime(end_date):
        raise HTTPException(
            status_code=400, detail="Start date must be before end date"
        )

    try:
        _ = get_coordinates(city=city)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    create_table(db_conn)
    creds = pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASS)
    connection_params = pika.ConnectionParameters(
        host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=creds
    )
    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()

    channel.queue_declare(queue=RABBITMQ_QUEUE)

    task_id = insert_db(db_conn)

    if task_id is None:
        raise HTTPException(status_code=400, detail="Could not start task")

    data_dict["task_id"] = task_id
    encoder = msgspec.msgpack.Encoder()
    body = encoder.encode(data_dict)

    channel.basic_publish(exchange="", routing_key=RABBITMQ_QUEUE, body=body)
    print("sent [x] data_dict")
    connection.close()

    return TaskDetails(task_id=task_id)
