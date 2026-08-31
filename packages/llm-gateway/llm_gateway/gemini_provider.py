from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import httpx

from llm_gateway.provider import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger('llm-gateway.gemini')


class GeminiProvider:
    name = 'gemini'

    def __init__(
        self,
        api_key: str | None = None,
        model: str = 'gemini-3.5-flash',
    ) -> None:
        self._api_key = api_key or os.environ.get('GEMINI_API_KEY', '')
        self._model = os.environ.get('GEMINI_MODEL', model)
        self._client: Any = None

        if self._api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                logger.warning('Could not initialize google-genai client, will use REST fallback: %s', e)
                self._client = None

    async def complete(self, request: LLMRequest) -> LLMResponse:
        start_time = time.monotonic()
        api_key = self._api_key or os.environ.get('GEMINI_API_KEY', '')

        if not api_key:
            raise ValueError(
                'GEMINI_API_KEY environment variable is missing. '
                'Please get a free API key at https://aistudio.google.com and set GEMINI_API_KEY.'
            )

        system_instruction = (request.system_prompt + '\n\n' + request.developer_prompt).strip()
        user_prompt = request.user_content

        if self._client is not None:
            try:
                from google.genai import types

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction if system_instruction else None,
                    temperature=request.temperature,
                    max_output_tokens=request.max_tokens,
                    response_mime_type='application/json' if request.output_schema else 'text/plain',
                )

                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self._model,
                    contents=user_prompt,
                    config=config,
                )

                latency_ms = int((time.monotonic() - start_time) * 1000)
                content = response.text or ''

                parsed = None
                try:
                    parsed = json.loads(content)
                except Exception:
                    parsed = None

                token_usage = {
                    'prompt_tokens': getattr(response.usage_metadata, 'prompt_token_count', 0) or 0,
                    'completion_tokens': getattr(response.usage_metadata, 'candidates_token_count', 0) or 0,
                    'total_tokens': getattr(response.usage_metadata, 'total_token_count', 0) or 0,
                }

                return LLMResponse(
                    content=content,
                    parsed=parsed,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                    provider='gemini',
                    model=self._model,
                    raw=response,
                )
            except Exception as e:
                logger.warning('google-genai SDK call failed, falling back to HTTP REST: %s', e)

        return await self._complete_via_rest(request, api_key, system_instruction, start_time)

    async def _complete_via_rest(
        self,
        request: LLMRequest,
        api_key: str,
        system_instruction: str,
        start_time: float,
    ) -> LLMResponse:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent'
        params = {'key': api_key}

        payload: dict[str, Any] = {
            'contents': [
                {
                    'parts': [{'text': request.user_content}]
                }
            ],
            'generationConfig': {
                'temperature': request.temperature,
                'maxOutputTokens': request.max_tokens,
            },
        }

        if system_instruction:
            payload['systemInstruction'] = {
                'parts': [{'text': system_instruction}]
            }

        if request.output_schema:
            payload['generationConfig']['responseMimeType'] = 'application/json'

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = int((time.monotonic() - start_time) * 1000)

        candidates = data.get('candidates', [])
        content = ''
        if candidates and 'content' in candidates[0] and 'parts' in candidates[0]['content']:
            parts = candidates[0]['content']['parts']
            content = ''.join(p.get('text', '') for p in parts)

        parsed = None
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = None

        usage = data.get('usageMetadata', {})
        token_usage = {
            'prompt_tokens': usage.get('promptTokenCount', 0),
            'completion_tokens': usage.get('candidatesTokenCount', 0),
            'total_tokens': usage.get('totalTokenCount', 0),
        }

        return LLMResponse(
            content=content,
            parsed=parsed,
            token_usage=token_usage,
            latency_ms=latency_ms,
            provider='gemini',
            model=self._model,
            raw=data,
        )
