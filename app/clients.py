import json
from typing import TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.schemas import Source

T = TypeVar("T", bound=BaseModel)


class UpstreamError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


async def call_model(
    http: httpx.AsyncClient, settings: Settings, system: str, user: str, schema: type[T]
) -> T:
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        settings.llm_token_limit_field: settings.llm_max_tokens,
    }
    # Some models do not accept temperature, so only send it when configured.
    if settings.llm_temperature is not None:
        payload["temperature"] = settings.llm_temperature
    try:
        response = await http.post(
            f"{str(settings.llm_base_url).rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"
            },
            json=payload,
            timeout=settings.llm_request_timeout,
        )
        response.raise_for_status()
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("Truncated model response")
        return schema.model_validate_json(choice["message"]["content"])
    except httpx.TimeoutException:
        raise UpstreamError("The language model timed out. Please try again.", 504) from None
    except httpx.HTTPError:
        raise UpstreamError("The language model is unavailable. Please try again.") from None
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, ValidationError):
        raise UpstreamError("The language model returned an invalid response.") from None


async def search_superhero(http: httpx.AsyncClient, api_key: str, name: str) -> list[Source]:
    url = f"https://superheroapi.com/api/{quote(api_key, safe='')}/search/"
    try:
        response = await http.get(url + quote(name, safe=""), timeout=20)
        response.raise_for_status()
        payload = response.json()
        if payload.get("response") == "error":
            if "not found" in str(payload.get("error", "")).lower():
                return []
            raise UpstreamError("The superhero provider rejected the request.")
        if payload.get("response") != "success" or not isinstance(payload.get("results"), list):
            raise ValueError("Invalid superhero response")
        results = payload["results"]
        if not all(isinstance(hero, dict) for hero in results):
            raise ValueError("Invalid superhero records")
        exact = [
            hero for hero in results if str(hero.get("name", "")).casefold() == name.casefold()
        ]
        matches = exact or results
        if len(matches) > 5:
            raise UpstreamError(
                "Too many superhero matches. Please use a more specific name.", 422
            )
        sources = []
        for hero in matches:
            hero_id = str(hero["id"])
            if not hero_id.isdigit() or not isinstance(hero["name"], str):
                raise ValueError("Invalid superhero identity")
            facts = {
                key: hero[key]
                for key in (
                    "name",
                    "powerstats",
                    "biography",
                    "appearance",
                    "work",
                    "connections",
                )
                if key in hero
            }
            sources.append(
                Source(
                    id=f"superhero:{hero_id}",
                    type="superhero_api",
                    title=f"{hero['name']} (record {hero_id})",
                    location="https://superheroapi.com/",
                    content=json.dumps(facts, ensure_ascii=False),
                )
            )
        return sources
    except httpx.TimeoutException:
        raise UpstreamError("The superhero provider timed out.", 504) from None
    except httpx.HTTPError:
        raise UpstreamError("The superhero provider is unavailable.") from None
    except (ValueError, KeyError, TypeError, AttributeError):
        raise UpstreamError("The superhero provider returned an invalid response.") from None
