"""Gemini-driven script generation. Adapted from MoneyPrinterTurbo with the fixes from v3."""
from __future__ import annotations
import re
from google import genai
from google.genai import types
from app.config import settings

PROMPT_TEMPLATE = """
# Role: Long-Form YouTube Video Script Generator

## Goals:
Generate a comprehensive long-form YouTube video script (~1800-2200 words total, targeting roughly 10-15 minutes of spoken narration at ~150 words per minute) on the given subject.

## Output structure (write the script in this exact order, as continuous narration — do NOT include section headings):
1. Hook (~40 words, ~15 seconds): why this is engaging, what the viewer will learn.
2. Setup / materials needed (~225 words, ~90 seconds).
3. Safety basics or context (~150 words, ~60 seconds).
4. Step-by-step method (~1,250 words, ~8-9 minutes — the longest section). Be SPECIFIC with numbers, times, temperatures, quantities. Walk through it sequentially as if guiding a beginner in real time.
5. Troubleshooting (~300 words, ~2 minutes): common problems, causes, fixes.
6. Variations (~225 words, ~90 seconds).
7. Outro (~75 words, ~30 seconds): cure/finish time, call to action, soft subscribe ask.

## Constraints:
1. Return as a single continuous string of natural spoken narration, with paragraph breaks (blank lines) at natural pause points.
2. Do not reference this prompt, the structure, or the word/time targets.
3. No "welcome to this video" boilerplate — start with the hook.
4. No markdown, headings, bullets, or stage directions.
5. Respond in the same language as the subject.

# Initialization:
- subject: {subject}
- target words: ~1800-2200
- target spoken duration: ~10-15 minutes
- paragraph count: at least 14
""".strip()

def _format(response: str) -> str:
    response = response.replace("*", "").replace("#", "")
    response = re.sub(r"\[.*?\]", "", response)
    # Add paragraph breaks if the model returned one big blob
    if "\n\n" not in response and len(response) > 1000:
        sentences = re.split(r"(?<=[.!?])\s+", response.strip())
        paras = ["\n".join(sentences[i : i + 5]) for i in range(0, len(sentences), 5)]
        response = "\n\n".join(paras)
    return response.strip()

def generate_script(subject: str, language: str = "en-US", target_paragraphs: int = 18) -> str:
    """Single Gemini call. Returns clean paragraph-broken script text."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    if target_paragraphs < 6:
        # Test/quick mode — much shorter script
        prompt = (
            f"Write a {target_paragraphs}-paragraph short video script (~150 words per paragraph) "
            f"about: {subject}. Plain prose, no markdown, no headings. Separate paragraphs with blank lines."
        )
    else:
        prompt = PROMPT_TEMPLATE.format(subject=subject)
    if language:
        prompt += f"\n- language: {language}"
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.5,
            top_p=1.0,
            top_k=40,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return _format(resp.text)

def generate_title(subject: str, script: str | None = None) -> str:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = f"Write a clear, engaging YouTube title (max 60 chars) for a how-to video on: {subject}. Reply with ONLY the title."
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.6, max_output_tokens=128,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return resp.text.strip().strip('"').strip()

def generate_paragraph_queries(paragraphs: list[str]) -> dict[int, list[str]]:
    """For each paragraph, ask Gemini for 2 specific YouTube search queries."""
    import json as _json
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    block = "\n".join(f"P{i}: {p}" for i, p in enumerate(paragraphs))
    prompt = f"""For each paragraph below, write 2 short, specific YouTube search queries that would return videos with B-roll matching what's spoken. Queries should focus on the concrete VISIBLE action being described.

PARAGRAPHS:
{block}

Return ONLY a single JSON object: {{"P0":["query1","query2"], ..., "P{len(paragraphs)-1}":["query1","query2"]}}
"""
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.3, max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    text = resp.text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {i: [paragraphs[i][:40]] for i in range(len(paragraphs))}
    data = _json.loads(m.group(0))
    out = {}
    for k, v in data.items():
        if k.startswith("P"):
            try: out[int(k[1:])] = v
            except: pass
    return out
