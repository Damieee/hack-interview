from __future__ import annotations

import base64
from pathlib import Path
from typing import Dict, List, Optional

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


async def answer_from_image(
    *,
    file: UploadFile,
    question: Optional[str],
    options: Optional[List[str]],
    model: Optional[str] = None,
) -> Dict[str, str]:
    data = await file.read()
    media_type = file.content_type or "image/png"
    encoded = base64.b64encode(data).decode("utf-8")
    data_url = f"data:{media_type};base64,{encoded}"

    question_text = question.strip() if question else ""
    if not question_text:
        question_text = (
            "Analyze this screenshot. Decide if it is a multiple-choice, coding/DSA, or system-design question. "
            "Follow the rules below."
        )

    option_block = ""
    normalized_options: List[str] = []
    if options:
        normalized_options = [opt.strip() for opt in options if opt.strip()]
        if normalized_options:
            option_block = "\n".join(
                f"Option {chr(65 + idx)}: {value}"
                for idx, value in enumerate(normalized_options)
            )

    system_prompt = (
        "You are an AI interview assistant.\n"
        "Rules:\n"
        "1. Multiple-choice prompt → respond ONLY with the winning option label and its text "
        "(e.g., 'Option C: Binary Search'). No extra commentary.\n"
        "2. Coding/DSA prompt → respond with a complete Python solution inside a ```python fenced block "
        "and nothing else (brief comments allowed). The code must be executable as-is.\n"
        "3. System design / architecture / diagram prompt → provide a detailed architecture description so the user "
        "can draw the diagram. Include high-level bullet points covering core components, data flow, storage, "
        "scaling/availability considerations, and technology choices.\n"
        "4. Otherwise, provide the most direct correct answer in one or two sentences."
    )

    content_blocks = [
        {"type": "input_text", "text": question_text},
    ]
    if option_block:
        content_blocks.append({"type": "input_text", "text": option_block})
    content_blocks.append({"type": "input_image", "image_url": data_url})

    def _call(extra_instruction: Optional[str] = None) -> str:
        user_blocks = content_blocks.copy()
        if extra_instruction:
            user_blocks = [
                {"type": "input_text", "text": extra_instruction},
                *user_blocks,
            ]
        logger.debug("Sending image question to model %s", model or settings.vision_model)
        response = client.responses.create(
            model=model or settings.vision_model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": user_blocks},
            ],
        )
        return response.output[0].content[0].text

    answer_text = _call()

    def needs_follow_up(text: str) -> bool:
        cleaned = text.strip().lower()
        placeholders = {
            "coding question",
            "open-ended/coding question",
            "open ended coding question",
            "this is a coding question",
            "write code",
            "system design",
            "system design question",
            "this screenshot contains open-ended/coding questions.",
        }
        return cleaned in placeholders or len(cleaned) < 40

    if not normalized_options and needs_follow_up(answer_text):
        logger.debug("Initial vision response looked incomplete; requesting explicit follow-up.")
        follow_up_instruction = (
            "Do not describe the question type. Instead, output the full answer.\n"
            "- For system design / architecture: provide a structured bullet list of components, data flow, scaling, "
            "and tech choices and explain in details how the system should be designed if the question says design or explain what the design is if the question says explain or if questions are asked about bottle neck of the system, explain well and better on how it can be improved, what can be added or removed or adjusted etc. just know how to answer any system design question you see.\n"
            "- For coding / DSA: output only a ```python fenced block containing the working solution.\n"
            "- Otherwise, respond with the direct answer in one or two sentences."
        )
        answer_text = _call(follow_up_instruction)

    selected_option: Optional[str] = None
    if normalized_options:
        for idx, _ in enumerate(normalized_options):
            label = f"Option {chr(65 + idx)}"
            if label.lower() in answer_text.lower():
                selected_option = label
                break

    return {"answer": answer_text, "selected_option": selected_option}
