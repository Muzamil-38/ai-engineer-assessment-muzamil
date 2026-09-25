import json
import re

import httpx

from app.clients import UpstreamError, call_model, search_superhero
from app.config import Settings
from app.prompts import ANSWER_PROMPT, ROUTING_PROMPT
from app.schemas import AskResponse, GeneratedAnswer, Route, Source


async def answer_question(
    question: str, http: httpx.AsyncClient, settings: Settings, sections: dict[str, Source]
) -> AskResponse:
    route = await choose_sources(question, http, settings, sections)

    sources, warnings = await fetch_sources(
        route, http, settings.superhero_api_key.get_secret_value(), sections
    )
    if not sources:
        if route.superhero_names:
            answer = "I couldn't find a matching superhero record. Please check the name."
        else:
            answer = (
                "I can answer questions about Cristiano Ronaldo's life and career "
                "and superheroes. "
                "I don't have a source for that question."
            )
        return AskResponse(answer=answer, sources=[], warnings=warnings)

    return await write_answer(question, sources, warnings, http, settings)


async def choose_sources(
    question: str, http: httpx.AsyncClient, settings: Settings, sections: dict[str, Source]
) -> Route:
    dataset = {key: section.content for key, section in sections.items()}
    route = await call_model(
        http, settings, ROUTING_PROMPT + "\n" + json.dumps(dataset), question, Route
    )
    for section_id in route.section_ids:
        if section_id not in sections:
            raise UpstreamError("The language model selected an unknown dataset section.")
    return route


async def fetch_sources(
    route: Route, http: httpx.AsyncClient, api_key: str, sections: dict[str, Source]
) -> tuple[list[Source], list[str]]:
    sources = {}
    for section_id in route.section_ids:
        source = sections[section_id]
        sources[source.id] = source

    warnings = []
    failures = []
    searched_names = set()
    for name in route.superhero_names:
        if name in searched_names:
            continue
        searched_names.add(name)
        try:
            matches = await search_superhero(http, api_key, name)
        except UpstreamError as error:
            failures.append(error)
            warnings.append(f"Could not retrieve {name}: {error}")
            continue

        if not matches:
            warnings.append(f"No superhero records found for {name}.")
        for source in matches:
            sources[source.id] = source

    if not sources and failures:
        raise failures[0]
    return list(sources.values()), warnings


async def write_answer(
    question: str, sources: list[Source], warnings: list[str],
    http: httpx.AsyncClient, settings: Settings,
) -> AskResponse:
    context = {
        "question": question,
        "sources": [source.model_dump() for source in sources],
        "warnings": warnings,
    }
    generated = await call_model(http, settings, ANSWER_PROMPT, json.dumps(context), GeneratedAnswer)

    available = {source.id: source for source in sources}
    selected_sources = {}
    for source_id in generated.source_ids:
        if source_id not in available:
            raise UpstreamError("The language model returned invalid source citations.")
        selected_sources[source_id] = available[source_id]

    citations = re.findall(r"\[((?:cr7|superhero):[^\]\n]+)\]", generated.answer)
    for source_id in citations:
        if source_id not in selected_sources:
            raise UpstreamError("The language model returned invalid source citations.")

    return AskResponse(
        answer=generated.answer,
        sources=list(selected_sources.values()),
        warnings=warnings,
    )
