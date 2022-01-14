from typing import TYPE_CHECKING, Optional, Union

import prisma
import strawberry
from prisma import Client, models
from prisma.types import TaskCreateInput
from starlette.applications import Starlette
from strawberry.asgi import GraphQL


@strawberry.type
class Location:
    id: strawberry.ID
    name: str

    @classmethod
    def marshal(cls, model: models.Location) -> "Location":
        return cls(id=strawberry.ID(str(model.id)), name=model.name)


@strawberry.type
class Task:
    id: strawberry.ID
    name: str
    location: Optional[Location] = None

    @classmethod
    def marshal(cls, model: models.Task) -> "Task":
        return cls(
            id=strawberry.ID(str(model.id)),
            name=model.name,
            location=Location.marshal(model.location) if model.location else None,
        )


@strawberry.type
class LocationNotFound:
    message: str = "Location with this name does not exist"


@strawberry.type
class LocationExists:
    message: str = "Location with this name already exist"


if TYPE_CHECKING:
    AddTaskResponse = Union[Task, LocationNotFound]
    AddLocationResponse = Union[Location, LocationExists]
else:
    AddTaskResponse = strawberry.union("AddTaskResponse", (Task, LocationNotFound))
    AddLocationResponse = strawberry.union("AddLocationResponse", (Location, LocationExists))


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def add_task(self, name: str, location_name: Optional[str]) -> AddTaskResponse:
        data: TaskCreateInput = {
            "name": name,
        }
        if location_name is not None:
            data["location"] = {
                "connect": {
                    "name": location_name,
                },
            }

        try:
            db_task = await models.Task.prisma().create(data=data)
        except prisma.errors.RecordNotFoundError:
            return LocationNotFound()

        return Task.marshal(db_task)

    @strawberry.mutation
    async def add_location(self, name: str) -> AddLocationResponse:
        try:
            location = await models.Location.prisma().create(
                data={
                    "name": name,
                },
            )
        except prisma.errors.UniqueViolationError:
            return LocationExists()

        return Location.marshal(location)


@strawberry.type
class Query:
    @strawberry.field
    async def tasks(self) -> list[Task]:
        # TODO: handle relational fields properly
        return [
            Task.marshal(task)
            for task in await models.Task.prisma().find_many(
                include={
                    "location": True,
                },
                order={
                    "name": "desc",
                },
            )
        ]

    @strawberry.field
    async def locations(self) -> list[Location]:
        return [
            Location.marshal(loc)
            for loc in await models.Location.prisma().find_many(
                order={
                    "name": "desc",
                },
            )
        ]


async def start_prisma() -> None:
    client = Client(auto_register=True)
    await client.connect()


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQL(schema)

app = Starlette(on_startup=[start_prisma])
app.add_route("/graphql", graphql_app)
