"""Optional, evidence-bound AI review for uncertain matches."""
import json
import os

import requests


class OpenAIReviewer:
    """Uses Structured Outputs; deterministic scores remain the source of truth."""
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def available(self):
        return bool(self.api_key)

    def review(self, original, candidate, match, website_text="", public_contacts=None):
        if not self.available:
            return {"status": "not_configured", "confidence": None, "reason": "OPENAI_API_KEY is not configured."}
        schema = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "recommendation": {"type": "string", "enum": ["confirm", "manual_review", "reject"]},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["recommendation", "confidence", "reason", "warnings"],
        }
        evidence = {"original": original, "candidate": candidate, "deterministic_match": match.to_dict(), "website_text": website_text[:5000], "public_contacts": public_contacts or {}}
        payload = {
            "model": self.model,
            "input": [{"role": "system", "content": "Return JSON only. Assess whether the candidate is the same public business. Do not invent evidence; recommend manual_review when evidence is insufficient."}, {"role": "user", "content": json.dumps(evidence)}],
            "text": {"format": {"type": "json_schema", "name": "business_review", "strict": True, "schema": schema}},
        }
        response = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload, timeout=30)
        response.raise_for_status()
        body = response.json()
        output = body.get("output_text")
        if not output:
            raise ValueError("AI response did not include structured output.")
        return json.loads(output)
