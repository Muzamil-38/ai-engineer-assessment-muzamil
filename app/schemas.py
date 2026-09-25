from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
HeroName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Question


class Source(BaseModel):
    id: str
    type: Literal["dataset", "superhero_api"]
    title: str
    location: str
    content: str


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    warnings: list[str] = Field(default_factory=list)


class Route(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section_ids: list[str] = Field(max_length=8)
    superhero_names: list[HeroName] = Field(max_length=3)


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=8000)
    source_ids: list[str] = Field(min_length=1)
