from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas import (
    DataQualityRequest,
    DataQualityResponse,
    MedicationReconcileRequest,
    MedicationReconcileResponse,
)
from app.llm import reconcile_medication, validate_data_quality


# ── Config ──────────────────────────────────────────────────────────────


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_key: str = "change-me-in-development"
    openai_api_key: str | None = None


settings = Settings()


# ── Auth ────────────────────────────────────────────────────────────────


async def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


# ── App ─────────────────────────────────────────────────────────────────


app = FastAPI(title="Clinical Data Reconciliation Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ──────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/reconcile/medication", response_model=MedicationReconcileResponse, dependencies=[Depends(verify_api_key)])
async def reconcile_medication_route(body: MedicationReconcileRequest) -> MedicationReconcileResponse:
    result = await reconcile_medication(body.model_dump())
    return MedicationReconcileResponse(**result)


@app.post("/api/validate/data-quality", response_model=DataQualityResponse, dependencies=[Depends(verify_api_key)])
async def validate_data_quality_route(body: DataQualityRequest) -> DataQualityResponse:
    result = await validate_data_quality(body.model_dump())
    return DataQualityResponse(**result)
