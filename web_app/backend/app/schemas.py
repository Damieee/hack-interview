from pydantic import BaseModel, Field


class InterviewResponse(BaseModel):
    transcript: str = Field(..., description="Verbatim transcription from Whisper.")
    quick_answer: str = Field(..., description="Concise response (~50 words).")
    full_answer: str = Field(..., description="Detailed response (~150 words).")


class HealthResponse(BaseModel):
    status: str

