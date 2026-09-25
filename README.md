# CR7 & Heroes

A FastAPI chatbot for Ronaldo and superhero questions, with sources included. It uses local Ronaldo notes, the Superhero API, and a hosted model through OpenRouter.

## Run

Start Docker. Copy `.env.example` to `.env` if needed, then set `LLM_API_KEY` and `SUPERHERO_API_KEY`.

A temporary OpenRouter review key is provided separately. You can also use any OpenAI-compatible provider by setting LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in .env. See .env.example for the configuration.

```sh
docker compose up --build -d
```

UI: http://localhost:8000
API docs: http://localhost:8000/docs

Stop with `docker compose down`.

## Approach

One model call selects sources; Python retrieves the data; a second call writes the answer. Source IDs are validated. The small dataset does not require a vector database.

## Tests

```sh
docker compose run --rm --no-deps -T \
  -v "$PWD/tests:/app/tests:ro" \
  api python -m unittest discover -s tests -v
```

Tests cover routing, validation, sources, and provider failures using mocked API calls.
