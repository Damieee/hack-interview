import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .config import Settings, get_settings
from .history import fetch_history_entries, save_history_entry
from .schemas import (
    HealthResponse,
    ImageQuestionResponse,
    HistoryEntry,
    InterviewResponse,
)
from .services import answer_from_image, process_interview


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    app = FastAPI(title="Interview Assistant API", version="0.1.0")

    async def get_session_id(x_session_id: str = Header(default=None, alias="X-Session-Id")) -> str:
        if x_session_id:
            return x_session_id
        return config.default_session_id

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allow_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/api/interview", response_model=InterviewResponse)
    async def interview_endpoint(
        file: UploadFile = File(..., description="Recorded audio blob."),
        position: str = Form(config.default_position),
        model: str = Form(config.default_model),
        job_description: str = Form("", description="Job description text"),
        company_info: str = Form("", description="Company overview text"),
        about_you: str = Form("", description="Candidate summary text"),
        resume: str = Form("", description="Resume highlights"),
        settings: Settings = Depends(get_settings),
        session_id: str = Depends(get_session_id),
    ) -> InterviewResponse:
        logger.info("Processing interview snippet for position %s", position)
        payload = await process_interview(
            file=file,
            position=position or settings.default_position,
            context_sections={
                "Job Description": job_description,
                "Company Info": company_info,
                "About You": about_you,
                "Resume": resume,
            },
            model=model or settings.default_model,
        )
        response = InterviewResponse(**payload)
        await save_history_entry(
            session_id,
            {
                "entry_type": "interview",
                "transcript": response.transcript,
                "quick_answer": response.quick_answer,
                "full_answer": response.full_answer,
                "position": position or settings.default_position,
                "model": model or settings.default_model,
            },
        )
        return response

    @app.post("/api/image-question", response_model=ImageQuestionResponse)
    async def image_question_endpoint(
        image: UploadFile = File(..., description="Photo or screenshot to analyze"),
        prompt: str = Form(
            "",
            description="Optional additional question text if the screenshot lacks context.",
        ),
        options: str = Form(
            "",
            description="Optional multi-line or semicolon separated answer choices.",
        ),
        model: Optional[str] = Form(None),
        session_id: str = Depends(get_session_id),
    ) -> ImageQuestionResponse:
        option_list: list[str] = []
        if options:
            if ";" in options:
                option_list = [part.strip() for part in options.split(";")]
            else:
                option_list = [line.strip() for line in options.splitlines()]

        payload = await answer_from_image(
            file=image,
            question=prompt,
            options=option_list,
            model=model or config.vision_model,
        )
        response = ImageQuestionResponse(**payload)
        await save_history_entry(
            session_id,
            {
                "entry_type": "vision",
                "answer": response.answer,
                "selected_option": response.selected_option,
                "prompt": prompt,
                "options": option_list,
                "model": model or config.vision_model,
            },
        )
        return response

    @app.get("/api/history", response_model=list[HistoryEntry])
    async def history_endpoint(session_id: str = Depends(get_session_id)) -> list[HistoryEntry]:
        return await fetch_history_entries(session_id)

    frontend_dist = os.getenv("FRONTEND_DIST")
    if frontend_dist:
        dist_path = Path(frontend_dist)
        if dist_path.is_dir():
            logger.info("Serving built frontend from %s", dist_path)
            app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="frontend")

    return app
