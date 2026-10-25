import msgspec


class DBStatus(msgspec.Struct):
    state: str


class TaskDetails(msgspec.Struct):
    task_id: str
