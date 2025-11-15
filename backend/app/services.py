from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from loguru import logger
from openai import BadRequestError, OpenAI
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
    temperature = 0.0 if short else 0.7
    request_kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
    }
    if temperature is not None:
        request_kwargs["temperature"] = temperature

    try:
        response = client.chat.completions.create(**request_kwargs)
    except BadRequestError as exc:
        message = str(exc).lower()
        if "temperature" in message:
            logger.warning(
                "Model %s rejected temperature=%s; retrying with default.",
                model,
                temperature,
            )
            request_kwargs.pop("temperature", None)
            response = client.chat.completions.create(**request_kwargs)
        else:
            raise
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


def _extract_response_text(response: object) -> str:
    output = getattr(response, "output", None) or []
    for block in output:
        contents = getattr(block, "content", None) or []
        for entry in contents:
            text = getattr(entry, "text", None)
            if text:
                return text
    fallback = getattr(response, "output_text", None)
    if isinstance(fallback, Sequence) and not isinstance(fallback, (str, bytes)):
        return " ".join(str(part) for part in fallback if part)
    if fallback:
        return str(fallback)
    logger.warning("Model response did not include text output.")
    return "Unable to extract response from model."


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
        "You are an AI interview assistant analyzing questions from screenshots or photos.\n"
        "\n"
        "Detect the question type and answer in the correct format. Never mention the question type in your answer.\n"
        "\n"
        "====================\n"
        "SYSTEM-DESIGN QUESTION DETECTION\n"
        "====================\n"
        "Treat the question as SYSTEM DESIGN if it includes ANY of these:\n"
        "- 'Design a system that...'\n"
        "- 'How would you design...'\n"
        "- 'Architecture for...'\n"
        "- 'High-level design / Low-level design'\n"
        "- Descriptions involving components like: API gateway, cache, load balancer, queue, microservices, workers.\n"
        "- Questions about scaling, reliability, storage, concurrency, or traffic.\n"
        "- Images/diagrams with boxes, arrows, flows, or service components.\n"
        "\n"
        "====================\n"
        "ANSWER FORMATS\n"
        "====================\n"
        "1. MULTIPLE-CHOICE → Return EXACTLY: `Option <letter>: <text>` (no explanations).\n"
        "\n"
        "2. CODING / DSA → ONLY executable Python in a ```python block (inline comments allowed).\n"
        "\n"
        "3. SYSTEM DESIGN → Provide a full solution with the sections:\n"
        "   • Overview\n"
        "   • Core Components\n"
        "   • Data Flow (step-by-step)\n"
        "   • Storage & Databases\n"
        "   • Scaling & Reliability\n"
        "   • Failure Handling\n"
        "   • Trade-offs & Alternatives\n"
        "\n"
        "   ***CRITICAL RULE: For every component you mention, include a short, beginner-friendly explanation immediately after the component name and how it is used in python.***\n"
        "   Example: \"Load Balancer (distributes incoming traffic across servers to prevent overload, most times i pip install it from x library or i get the credentials from aws and use it within my system)\".\n"
        "   These explanations must be concise but informative.\n"
        "\n"
        "4. ANY OTHER QUESTION → Answer in four clear sentences.\n"
        "\n"
        "====================\n"
        "IMPORTANT RULES\n"
        "====================\n"
        "- Never identify the question type in your output.\n"
        "- Never summarize the prompt.\n"
        "- For system design: always provide concrete, detailed, sequential architecture.\n"
        "- Explanations must appear immediately next to each component.\n"
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
        return _extract_response_text(response)

    def needs_follow_up(text: str) -> bool:
        cleaned = text.strip().lower()
        if not cleaned:
            return True
        classification_snippets = [
            "system design question",
            "this is a system design",
            "not coding/dsa",
            "not multiple-choice",
            "multiple choice question",
            "this screenshot lists prompts",
            "identify the question type",
        ]
        if any(snippet in cleaned for snippet in classification_snippets):
            return True
        if len(cleaned) < 120 and ("system design" in cleaned or "coding question" in cleaned):
            return True
        return False

    answer_text = _call()

    if needs_follow_up(answer_text):
        logger.debug("Vision reply looked like a classification; requesting full solution.")
        follow_up_instruction = (
            "Provide the complete answer, not a classification. "
            "If the screenshot lists multiple system design prompts, give a structured response for each item "
            "using the required sections (Overview, Components, Data Flow, Storage, Scaling, Trade-offs). "
            "Never mention that it is a system-design question; just deliver the design(s)."
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
