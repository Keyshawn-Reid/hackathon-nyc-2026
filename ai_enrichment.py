"""
ai_enrichment.py
----------------
Text-based work-order and field-observation enrichment using GPT-4o.
Returns the same schema as projectnyc_vision.py plus workflow fields.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_FALLBACK = {
    "issue_type": "Unknown",
    "visible_evidence": [],
    "likely_asset_or_system": "Unknown",
    "severity": "medium",
    "confidence_label": "Needs Inspection",
    "affected_users": "Unknown — on-site verification required",
    "missing_information": ["Manual inspection required"],
    "recommended_action": "Submit to facilities coordinator for manual review.",
    "criticalasset_update_draft": "Automated analysis unavailable. Please review manually.",
    "compliance_context": "",
    "operational_implications": "",
    "escalation_path": "",
    "closure_verification": "",
    "root_cause_categories": [],
    "suggested_assignment_group": "",
}

_SYSTEM = """\
You are an expert NYC school and facilities operations analyst.
Transform facility observations and work orders into structured, actionable intelligence.

Rules:
- Be specific and action-oriented. Keep language professional and concise.
- confidence_label must be exactly one of: Verified, Likely, Inferred, Missing, Needs Inspection, Conflicting
- severity must be exactly one of: low, medium, high
- issue_type must match one of the listed categories exactly.
- Return ONLY valid JSON matching the schema. No markdown fences, no explanation.
"""

_SCHEMA = """\
{
  "issue_type": "HVAC / Ventilation | Plumbing / Water | Electrical / Lighting | Structural / Safety | Pest / Sanitation | Mold / Air Quality | Elevator / Accessibility | Fire Safety / Sprinkler | Unknown",
  "visible_evidence": ["list of specific evidence items from the description"],
  "likely_asset_or_system": "specific asset or system involved",
  "severity": "low | medium | high",
  "confidence_label": "Verified | Likely | Inferred | Missing | Needs Inspection | Conflicting",
  "affected_users": "who is impacted and scope",
  "missing_information": ["what is needed to confirm or act on this"],
  "recommended_action": "single most important next step for the facility team",
  "criticalasset_update_draft": "one-paragraph work order draft suitable for CriticalAsset",
  "compliance_context": "relevant NYC code, inspection requirement, or regulatory obligation — 1-2 sentences",
  "operational_implications": "what happens if this is not addressed — 1-2 sentences",
  "escalation_path": "who should own this and when to escalate — 1 sentence",
  "closure_verification": "one question the reporter should answer to confirm the issue is resolved",
  "root_cause_categories": ["list 2-4 likely root causes"],
  "suggested_assignment_group": "e.g. HVAC Mechanic, Licensed Plumber, Electrical Contractor, Building Engineer"
}
"""


def enrich_text_signal(description: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Analyze this NYC facility issue and return structured intelligence:\n\n"
                    f"{description}\n\n"
                    f"Return ONLY JSON matching this schema:\n{_SCHEMA}"
                ),
            },
        ],
        max_tokens=800,
        temperature=0.2,
    )
    return _parse(response.choices[0].message.content)


def enrich_work_order(wo: dict) -> dict:
    title = wo.get("title", "")
    desc = wo.get("description", "") or "(none provided)"
    priority = wo.get("executionPriority", "")
    severity = wo.get("severity", "")
    stage = (wo.get("workOrderStage") or {}).get("name", "")
    loc = (wo.get("location") or {}).get("locationName", "")
    addr = (wo.get("location") or {}).get("address", "")

    context = (
        f"Existing work order:\n"
        f"Title: {title}\n"
        f"Description: {desc}\n"
        f"Priority: {priority}  |  Severity: {severity}  |  Stage: {stage}\n"
        f"Location: {loc} {addr}\n\n"
        f"This work order may be weak or under-described. "
        f"Enrich it with better analysis, root cause categories, and a clear recommended action."
    )

    return enrich_text_signal(context)


def _parse(text: str) -> dict:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.strip()
    try:
        parsed = json.loads(clean)
        for k, v in _FALLBACK.items():
            if k not in parsed:
                parsed[k] = v
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[ai_enrichment] parse error: {e}")
        return dict(_FALLBACK)
