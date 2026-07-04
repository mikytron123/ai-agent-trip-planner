import time
from pathlib import Path

import httpx
import pytest
from python_on_whales import docker
from testcontainers.core.container import DockerContainer, Network


@pytest.fixture(scope="module")
def api_container():
    network = Network()
    network.create()
    postgres_container = DockerContainer("postgres:latest")
    postgres_container.with_exposed_ports(5432)

    postgres_container.with_env("POSTGRES_USER", "postgres")
    postgres_container.with_env("POSTGRES_PASSWORD", "postgres")
    postgres_container.with_env("POSTGRES_DB", "postgres")
    postgres_container.with_network(network)
    postgres_container.with_network_aliases("db")
    # postgres_container = PostgresContainer(
    #     username="postgres", password="postgres", dbname="postgres"
    # )
    postgres_container.start()
    rabbitmq_container = DockerContainer(image="rabbitmq:3-management")
    rabbitmq_container.with_exposed_ports(5672)
    rabbitmq_container.with_exposed_ports(15672)
    rabbitmq_container.with_env("RABBITMQ_DEFAULT_USER", "user")
    rabbitmq_container.with_env("RABBITMQ_DEFAULT_PASS", "password")
    rabbitmq_container.with_network(network)
    rabbitmq_container.with_network_aliases("rabbitmq")
    # rabbitmq_container = RabbitMqContainer(image="rabbitmq:3-management",username="user", password="password")
    rabbitmq_container.start()
    rustfs_container = DockerContainer("rustfs/rustfs:latest")
    rustfs_container.with_exposed_ports(9000)
    rustfs_container.with_env("RUSTFS_ACCESS_KEY", "rustfsadmin")
    rustfs_container.with_env("RUSTFS_SECRET_KEY", "rustfsadmin")
    rustfs_container.with_env("RUSTFS_CONSOLE_ENABLE", "true")
    rustfs_container.with_network(network)
    rustfs_container.with_network_aliases("rustfs")
    rustfs_container.start()

    api_img = docker.build((Path(__file__).parent / "../backend").resolve(True))
    api_container = DockerContainer(image=str(api_img))
    api_container.with_network(network)
    api_container.with_exposed_ports(8000)
    api_container.with_env("USE_MOCK", "true")

    api_container.with_env("POSTGRES_HOST", "db")
    api_container.with_env("POSTGRES_USER", "postgres")
    api_container.with_env("POSTGRES_DB", "postgres")
    api_container.with_env("POSTGRES_PASS", "postgres")
    api_container.with_env(
        "POSTGRES_PORT",
        "5432",
    )

    api_container.with_env("RABBITMQ_USER", "user")
    api_container.with_env("RABBITMQ_PASS", "password")
    api_container.with_env("RABBITMQ_HOST", "rabbitmq")
    api_container.with_env(
        "RABBITMQ_PORT",
        "5672",
    )
    api_container.with_env("RABBITMQ_QUEUE", "messages")
    api_container.with_env("RUSTFS_HOST", "rustfs")
    api_container.with_env("RUSTFS_PORT", "9000")
    api_container.with_env("RUSTFS_ACCESS_KEY", "rustfsadmin")
    api_container.with_env("RUSTFS_SECRET_KEY", "rustfsadmin")
    api_container.with_env("RUSTFS_BUCKET", "llm")

    worker_img = docker.build((Path(__file__).parent / "../worker").resolve(True))
    worker_container = DockerContainer(str(worker_img))
    worker_container.with_network(network)
    worker_container.with_env("USE_MOCK", "true")
    worker_container.with_env("POSTGRES_HOST", "db")
    worker_container.with_env("POSTGRES_USER", "postgres")
    worker_container.with_env("POSTGRES_DB", "postgres")
    worker_container.with_env("POSTGRES_PASS", "postgres")
    worker_container.with_env(
        "POSTGRES_PORT",
        "5432",
    )

    worker_container.with_env("RABBITMQ_USER", "user")
    worker_container.with_env("RABBITMQ_PASS", "password")
    worker_container.with_env("RABBITMQ_HOST", "rabbitmq")
    worker_container.with_env(
        "RABBITMQ_PORT",
        "5672",
    )
    worker_container.with_env("RABBITMQ_QUEUE", "messages")
    worker_container.with_env("RUSTFS_HOST", "rustfs")
    worker_container.with_env("RUSTFS_PORT", "9000")
    worker_container.with_env("RUSTFS_ACCESS_KEY", "rustfsadmin")
    worker_container.with_env("RUSTFS_SECRET_KEY", "rustfsadmin")
    worker_container.with_env("RUSTFS_BUCKET", "llm")
    time.sleep(5)
    worker_container.start()

    api_container.start()

    yield api_container

    api_container.stop()
    worker_container.stop()
    rustfs_container.stop()
    rabbitmq_container.stop()
    postgres_container.stop()
    network.remove()


def test_e2e(api_container):
    time.sleep(15)
    host = api_container.get_container_host_ip()
    exposed_port = api_container.get_exposed_port(8000)
    url = f"http://{host}:{exposed_port}"
    resp = httpx.post(
        f"{url}/task/start",
        json={"city": "Toronto", "start_date": "2024-02-01", "end_date": "2024-02-02"},
    )

    assert resp.status_code == 202
    task_id = resp.json()["task_id"]
    retries = 0
    while httpx.get(f"{url}/tasks/{task_id}/status").json()["state"] != "done":
        if retries >= 3:
            pytest.fail("failed to get output after 3 retries")
        time.sleep(5)
        retries += 1

    resp2 = httpx.get(f"{url}/tasks/{task_id}/output")
    assert resp2.status_code == 200
    assert resp2.json() == "test"
