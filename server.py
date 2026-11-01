"""Local JSON API and static JavaScript frontend for Lead Intelligence."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lead_intelligence.planner import create_plan, execute_plan
from lead_intelligence.commands import apply_command, parse_command
from lead_intelligence.extraction import extract_website_contacts
from lead_intelligence.verification import verify_rows_with_places


ROOT = Path(__file__).parent
app = FastAPI(title="AI-Assisted Lead Intelligence API")
app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")


class PlanRequest(BaseModel):
    url: str
    prompt: str = "Extract public business names, addresses, phone numbers, emails, and websites."
    browser_mode: bool = False
    max_records: int = Field(default=100, ge=1, le=500)


class ExecuteRequest(BaseModel):
    plan: dict


class RecordCommandRequest(BaseModel):
    records: list
    prompt: str


class LeadGenerationRequest(BaseModel):
    records: list
    name_field: str = "business_name"
    address_field: str = "business_address"
    city_field: str = "city"
    postal_field: str = "postal_code"


@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.post("/api/plan")
def plan(request: PlanRequest):
    try:
        return create_plan(request.url, request.prompt, request.browser_mode, request.max_records).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/api/execute")
def execute(request: ExecuteRequest):
    try:
        return execute_plan(request.plan)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/api/records/command")
def records_command(request: RecordCommandRequest):
    command = parse_command(request.prompt)
    if command.action == "unknown":
        raise HTTPException(status_code=400, detail="Use a supported operation such as remove, exclude, keep, or include.")
    kept, excluded = apply_command(request.records, command)
    return {"command": command.action, "kept": kept, "excluded": excluded}


@app.post("/api/leads/generate")
def generate_leads(request: LeadGenerationRequest):
    try:
        results = verify_rows_with_places(
            request.records,
            request.name_field,
            request.address_field,
            request.city_field,
            request.postal_field,
        )
        for row in results:
            website = row.get("places_website", "") or row.get("website", "")
            if website:
                details = extract_website_contacts(website, max_pages=3)
                row["verified_public_email"] = "; ".join(details.get("emails", [])) or row.get("public_email", "")
                row["verified_public_phone"] = "; ".join(details.get("phones", [])) or row.get("places_phone", "") or row.get("public_phone", "")
                row["verified_contact_evidence_urls"] = "; ".join(details.get("source_urls", []))
            else:
                row["verified_public_email"] = row.get("public_email", "")
                row["verified_public_phone"] = row.get("places_phone", "") or row.get("public_phone", "")
                row["verified_contact_evidence_urls"] = row.get("places_source_url", "")
        contacts = [
            row for row in results
            if row.get("places_verification_status") in {"Verified", "Probable Match"}
            and (row.get("verified_public_phone") or row.get("verified_public_email"))
        ]
        return {"records": results, "contacts": contacts, "record_count": len(results), "contact_count": len(contacts)}
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))