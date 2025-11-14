from fastapi import Depends, FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import Settings, get_settings
from .schemas import HealthResponse, InterviewResponse
from .services import process_interview


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    app = FastAPI(title="Interview Assistant API", version="0.1.0")

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
        return InterviewResponse(**payload)

    return app
