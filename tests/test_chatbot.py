import json
import os
import unittest
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.dataset import load_sections
from app.main import app


class ChatbotTests(unittest.TestCase):
    @contextmanager
    def client(self, replies, hero_status=200, hero_reply=None):
        """Run the real app with fake HTTP responses and no real credentials."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(
                _env_file=None,
                SUPERHERO_API_KEY="test-hero-key",
                LLM_BASE_URL="https://model.example/v1",
                LLM_API_KEY="test-model-key",
                LLM_MODEL="test-model",
            )
        remaining = iter(replies)
        self.requests = []

        def handle(request):
            self.requests.append(request)
            if request.url.host == "model.example":
                reply = next(remaining)
                if isinstance(reply, Exception):
                    raise reply
                content = reply if isinstance(reply, str) else json.dumps(reply)
                return httpx.Response(200, json={
                    "choices": [{"finish_reason": "stop", "message": {"content": content}}]
                })
            self.assertEqual(request.url.host, "superheroapi.com")
            self.assertEqual(request.url.path, "/api/test-hero-key/search/Batman")
            body = hero_reply if hero_reply is not None else {
                "response": "success",
                "results": [{
                    "id": "70", "name": "Batman",
                    "biography": {"full-name": "Bruce Wayne"},
                }],
            }
            return httpx.Response(hero_status, json=body)

        @asynccontextmanager
        async def lifespan(application):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
                application.state.http = http
                application.state.settings = settings
                application.state.sections = load_sections()
                yield

        with patch.object(app.router, "lifespan_context", lifespan), TestClient(app) as client:
            yield client

    def test_dataset_superhero_and_mixed_questions(self):
        cases = [
            ("Where was Ronaldo born?", ["biography"], [],
             "Ronaldo was born in Funchal.", ["cr7:biography"]),
            ("Who is Batman?", [], ["Batman"],
             "Batman is Bruce Wayne.", ["superhero:70"]),
            ("Where was Ronaldo born and who is Batman?", ["biography"], ["Batman"],
             "Ronaldo was born in Funchal. Batman is Bruce Wayne.",
             ["cr7:biography", "superhero:70"]),
        ]
        for question, sections, heroes, answer, source_ids in cases:
            with self.subTest(question=question), self.client([
                {"section_ids": sections, "superhero_names": heroes},
                {"answer": answer, "source_ids": source_ids},
            ]) as client:
                response = client.post("/ask", json={"question": question})
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["answer"], answer)
                self.assertEqual([s["id"] for s in body["sources"]], source_ids)
                self.assertTrue(all(s["content"] and s["location"] for s in body["sources"]))
                self.assertEqual(body["warnings"], [])
                self.assertNotIn("test-hero-key", response.text)
                model_calls = [r for r in self.requests if r.url.host == "model.example"]
                self.assertEqual(len(model_calls), 2)
                payload = json.loads(model_calls[0].content)
                self.assertEqual(payload["model"], "test-model")
                self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_bad_input_never_calls_providers(self):
        for body in ({}, {"question": " "}, {"question": 42}, {"question": "x" * 2001}):
            with self.subTest(body=body), self.client([]) as client:
                response = client.post("/ask", json=body)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(self.requests, [])

    def test_unrelated_question_skips_second_model_call(self):
        with self.client([{"section_ids": [], "superhero_names": []}]) as client:
            response = client.post("/ask", json={"question": "What is the weather?"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["sources"], [])
            self.assertEqual(len(self.requests), 1)

    def test_invalid_model_output_is_rejected(self):
        for reply in ("not JSON", {"section_ids": ["missing"], "superhero_names": []}):
            with self.subTest(reply=reply), self.client([reply]) as client:
                response = client.post("/ask", json={"question": "Who is Ronaldo?"})
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json()["sources"], [])

    def test_invented_source_is_rejected(self):
        with self.client([
            {"section_ids": ["biography"], "superhero_names": []},
            {"answer": "An unsupported answer.", "source_ids": ["cr7:invented"]},
        ]) as client:
            response = client.post("/ask", json={"question": "Where was Ronaldo born?"})
            self.assertEqual(response.status_code, 502)

    def test_model_timeout_returns_safe_error(self):
        with self.client([httpx.ReadTimeout("private-provider-details")]) as client:
            response = client.post("/ask", json={"question": "Who is Batman?"})
            self.assertEqual(response.status_code, 504)
            self.assertNotIn("private-provider-details", response.text)

    def test_missing_hero_returns_warning(self):
        with self.client(
            [{"section_ids": [], "superhero_names": ["Batman"]}],
            hero_reply={"response": "error", "error": "character with given name not found"},
        ) as client:
            response = client.post("/ask", json={"question": "Who is Batman?"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["sources"], [])
            self.assertTrue(response.json()["warnings"])

    def test_provider_failure_without_other_data_returns_error(self):
        with self.client(
            [{"section_ids": [], "superhero_names": ["Batman"]}], hero_status=503
        ) as client:
            response = client.post("/ask", json={"question": "Who is Batman?"})
            self.assertEqual(response.status_code, 502)

    def test_partial_failure_keeps_available_answer(self):
        with self.client([
            {"section_ids": ["biography"], "superhero_names": ["Batman"]},
            {"answer": "Ronaldo was born in Funchal. Batman data is unavailable.",
             "source_ids": ["cr7:biography"]},
        ], hero_status=503) as client:
            response = client.post("/ask", json={"question": "Where was Ronaldo born and who is Batman?"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["sources"]), 1)
            self.assertTrue(response.json()["warnings"])


if __name__ == "__main__":
    unittest.main()
