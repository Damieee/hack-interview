from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InterviewResponse(BaseModel):
    transcript: str = Field(..., description="Verbatim transcription from Whisper.")
    quick_answer: str = Field(..., description="Concise response (~50 words).")
    full_answer: str = Field(..., description="Detailed response (~150 words).")


class HealthResponse(BaseModel):
    status: str


class ImageQuestionResponse(BaseModel):
    answer: str = Field(..., description="Model's answer or explanation.")
    selected_option: str | None = Field(
        default=None, description="Chosen option (if provided)."
    )


class HistoryEntry(BaseModel):
    id: str
    entry_type: Literal["interview", "vision"]
    created_at: datetime
    transcript: str | None = None
    quick_answer: str | None = None
    full_answer: str | None = None
    answer: str | None = None
    selected_option: str | None = None
    prompt: str | None = None
    options: list[str] | None = None
    position: str | None = None
    model: str | None = None
