import csv
import io
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

app = FastAPI(title="VC Automation UI")
security = HTTPBasic()
templates = Jinja2Templates(directory="templates")

DATA_PATH = Path("data/companies.json")


def _default_companies() -> list[dict[str, Any]]:
    now = datetime.utcnow().strftime("%Y-%m-%d")
    return [
        {
            "id": "acme-ai",
            "name": "Acme AI",
            "fit_label": "high",
            "verticals": ["AI", "Developer Tools"],
            "stage_guess": "Seed",
            "last_updated": now,
            "evidence": [
                "Raised a $3M pre-seed in 2024.",
                "Built an AI-powered observability copilot.",
            ],
            "extracted_facts": {
                "team_size": "12",
                "hq": "San Francisco, CA",
                "revenue_model": "Usage-based SaaS",
            },
            "reasons": [
                "Strong technical founding team.",
                "Fast product iteration from launch notes.",
            ],
            "risks": [
                "Crowded observability market.",
                "Early GTM motion still forming.",
            ],
            "questions": [
                "How sticky is weekly active usage among design partners?",
                "What is expansion strategy beyond engineering teams?",
            ],
            "outreach_draft": "Hi Acme team—impressed by your pace in AI observability. We'd love to learn more about your roadmap and how you're thinking about scaling GTM post-seed.",
        },
        {
            "id": "bioflux",
            "name": "BioFlux",
            "fit_label": "medium",
            "verticals": ["Healthcare", "BioTech"],
            "stage_guess": "Series A",
            "last_updated": now,
            "evidence": [
                "Published FDA pilot results.",
                "Hiring Head of Clinical Ops.",
            ],
            "extracted_facts": {
                "team_size": "34",
                "hq": "Boston, MA",
                "revenue_model": "Enterprise contracts",
            },
            "reasons": ["Strong regulatory progress."],
            "risks": ["Long enterprise sales cycles."],
            "questions": ["Current payer strategy and partnerships?"],
            "outreach_draft": "Hi BioFlux team—congrats on your recent pilot milestones. We'd enjoy hearing where you see the biggest unlocks ahead of your next growth phase.",
        },
    ]


def _ensure_data_file() -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        DATA_PATH.write_text(json.dumps(_default_companies(), indent=2), encoding="utf-8")


def load_companies() -> list[dict[str, Any]]:
    _ensure_data_file()
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def check_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    expected_user = os.getenv("BASIC_AUTH_USER", "admin")
    expected_pass = os.getenv("BASIC_AUTH_PASS", "changeme")

    user_ok = secrets.compare_digest(credentials.username, expected_user)
    pass_ok = secrets.compare_digest(credentials.password, expected_pass)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def apply_filters(
    companies: list[dict[str, Any]],
    vertical: str | None,
    stage: str | None,
    fit_label: str | None,
) -> list[dict[str, Any]]:
    filtered = companies
    if vertical:
        filtered = [c for c in filtered if vertical in c.get("verticals", [])]
    if stage:
        filtered = [c for c in filtered if c.get("stage_guess") == stage]
    if fit_label:
        filtered = [c for c in filtered if c.get("fit_label") == fit_label]
    return filtered


@app.get("/", response_class=HTMLResponse)
def company_list(
    request: Request,
    _: str = Depends(check_auth),
    vertical: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    fit_label: str | None = Query(default=None),
):
    companies = load_companies()
    filtered = apply_filters(companies, vertical, stage, fit_label)

    all_verticals = sorted({v for c in companies for v in c.get("verticals", [])})
    all_stages = sorted({c.get("stage_guess") for c in companies if c.get("stage_guess")})
    all_fit_labels = sorted({c.get("fit_label") for c in companies if c.get("fit_label")})

    return templates.TemplateResponse(
        "list.html",
        {
            "request": request,
            "companies": filtered,
            "all_verticals": all_verticals,
            "all_stages": all_stages,
            "all_fit_labels": all_fit_labels,
            "selected": {"vertical": vertical, "stage": stage, "fit_label": fit_label},
        },
    )


@app.get("/company/{company_id}", response_class=HTMLResponse)
def company_detail(request: Request, company_id: str, _: str = Depends(check_auth)):
    companies = load_companies()
    company = next((c for c in companies if c.get("id") == company_id), None)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return templates.TemplateResponse("detail.html", {"request": request, "company": company})


@app.get("/export/json")
def export_json(
    _: str = Depends(check_auth),
    vertical: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    fit_label: str | None = Query(default=None),
):
    companies = apply_filters(load_companies(), vertical, stage, fit_label)
    return JSONResponse(content=companies)


@app.get("/export/csv")
def export_csv(
    _: str = Depends(check_auth),
    vertical: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    fit_label: str | None = Query(default=None),
):
    companies = apply_filters(load_companies(), vertical, stage, fit_label)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "name", "fit_label", "verticals", "stage_guess", "last_updated"],
    )
    writer.writeheader()
    for company in companies:
        writer.writerow(
            {
                "id": company.get("id", ""),
                "name": company.get("name", ""),
                "fit_label": company.get("fit_label", ""),
                "verticals": ", ".join(company.get("verticals", [])),
                "stage_guess": company.get("stage_guess", ""),
                "last_updated": company.get("last_updated", ""),
            }
        )

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=companies.csv"},
    )
