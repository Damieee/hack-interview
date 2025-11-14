from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from loguru import logger
from openai import OpenAI
from starlette.datastructures import UploadFile

from .config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)

SYS_PREFIX = "You are interviewing for a "
SYS_SUFFIX = (
    " position. You will receive an audio transcription of the question. "
    "Understand the question and answer it clearly.\n"
)
SHORT_INSTRUCTION = "Concisely respond, limiting your answer to 50 words."
LONG_INSTRUCTION = (
    "Before answering, think step by step and reply in no more than 150 words."
)


def build_context_prompt(position: str, context: str, short: bool) -> str:
    prompt = SYS_PREFIX + position + SYS_SUFFIX
    prompt += SHORT_INSTRUCTION if short else LONG_INSTRUCTION
    trimmed = context.strip()
    if trimmed:
        prompt += "\n\nReference Information:\n" + trimmed
    return prompt


async def transcribe_audio(file: UploadFile) -> str:
    filename = Path(file.filename or "audio.webm").name
    logger.debug("Transcribing %s", filename)
    data = await file.read()
    transcript: str = client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, data),
        response_format="text",
    )
    logger.debug("Transcription completed")
    return transcript


def generate_answer(
    transcript: str,
    *,
    position: str,
    context: str,
    short: bool,
    model: str,
) -> str:
    prompt = build_context_prompt(position, context, short)
    logger.debug("Generating %s answer", "short" if short else "full")
    response = client.chat.completions.create(
        model=model,
        temperature=0.0 if short else 0.7,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
    )
    return response.choices[0].message.content


async def process_interview(
    *,
    file: UploadFile,
    position: str,
    context_sections: Dict[str, str],
    model: str,
) -> Dict[str, str]:
    transcript = await transcribe_audio(file)
    merged_context = "\n\n".join(
        f"{label}: {value.strip()}"
        for label, value in context_sections.items()
        if value and value.strip()
    ).strip()

    quick_answer = generate_answer(
        transcript,
        position=position,
        context=merged_context,
        short=True,
        model=model,
    )
    full_answer = generate_answer(
        transcript,
        position=position,
        context=merged_context,
        short=False,
        model=model,
    )
    return {
        "transcript": transcript,
        "quick_answer": quick_answer,
        "full_answer": full_answer,
    }
