import uuid

import boto3
import pytest
from botocore.client import Config
from testcontainers.core.container import DockerContainer

from backend.app import read_text_from_rustfs
from worker.recieve import upload_text_to_rustfs

# path = os.getcwd()
# parent_path = Path(__file__).parent.resolve()

# if str(parent_path) not in sys.path:
#     sys.path.append(str(parent_path))
# if path not in sys.path:
#     sys.path.append(path)

# print(sys.path)


@pytest.fixture(scope="module")
def rustfs_container():

    rustfs_container = DockerContainer("rustfs/rustfs:latest")
    rustfs_container.with_exposed_ports(9000)
    rustfs_container.with_env("RUSTFS_ACCESS_KEY", "rustfsadmin")
    rustfs_container.with_env("RUSTFS_SECRET_KEY", "rustfsadmin")
    rustfs_container.with_env("RUSTFS_CONSOLE_ENABLE", "true")
    rustfs_container.start()

    yield rustfs_container

    rustfs_container.stop()


def test_read_and_write(rustfs_container):
    host_ip = rustfs_container.get_container_host_ip()
    exposed_port = rustfs_container.get_exposed_port(9000)

    RUSTFS_ENDPOINT = f"http://{host_ip}:{exposed_port}"
    RUSTFS_ACCESS_KEY = "rustfsadmin"
    RUSTFS_SECRET_KEY = "rustfsadmin"
    client = boto3.client(
        "s3",
        endpoint_url=RUSTFS_ENDPOINT,
        aws_access_key_id=RUSTFS_ACCESS_KEY,
        aws_secret_access_key=RUSTFS_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )

    task_id = str(uuid.uuid4())
    text_content = "Sample Text"
    upload_text_to_rustfs(client, "test", f"{task_id}.txt", text_content)
    uploaded_text = read_text_from_rustfs(client, "test", f"{task_id}.txt")
    assert text_content == uploaded_text
