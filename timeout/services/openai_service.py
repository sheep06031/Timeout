"""
openai_service.py - Provides utility functions to interact with the OpenAI API for generating chat completions and parsing JSON responses, including handling markdown code fences in the output.
"""

import json
from django.conf import settings


def strip_code_fence(raw):
    """Remove markdown code fences from a string."""
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    return raw


def call_openai(messages, max_tokens=300, temperature=0):
    """Call OpenAI chat completions. Returns raw response string or raises."""
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def call_openai_json(messages, max_tokens=300, temperature=0):
    """Call OpenAI and return parsed JSON. Raises json.JSONDecodeError if invalid."""
    raw = call_openai(messages, max_tokens=max_tokens, temperature=temperature)
    return json.loads(strip_code_fence(raw))
