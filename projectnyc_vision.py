"""
projectnyc_vision.py
--------------------
Analyze a student-submitted facility photo (and optional text context)
and return structured operational intelligence for NYC school/facility teams.

Usage:
    result = analyze_signal_image("photo.jpg", optional_context="No heat in room 204")
    print(result)  # dict matching OUTPUT_SCHEMA

Environment:
    OPENAI_API_KEY  — required, loaded from .env
"""

import os
import base64
import json
import io
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Image compression ────────────────────────────────────────────────────────

MAX_DIMENSION = 1600
JPEG_QUALITY  = 85

def _compress_image(image_path: str) -> bytes:
    """Resize and JPEG-compress an image to keep token cost low."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return buf.getvalue()


def encode_image(image_path: str) -> str:
    """Return a base64-encoded JPEG string ready for the OpenAI vision API."""
    return base64.b64encode(_compress_image(image_path)).decode("utf-8")


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert NYC school and facilities analyst.
You help operations teams turn student-submitted photos of building problems
into structured, actionable intelligence.

Rules:
- Do not overclaim certainty. Use the confidence labels honestly.
- Only mark confidence as "Verified" when the image clearly and unambiguously supports it.
- Use "Needs Inspection" whenever physical verification is required before action.
- Use "Inferred" when the issue is plausible but not fully visible.
- Use "Missing" when critical evidence is absent from the image.
- Use "Conflicting" when evidence in the image contradicts the text context.
- Keep language professional, concise, and action-oriented.
- Always recommend human inspection for high-severity or ambiguous issues.
- Affected users should describe who is impacted (e.g., "Students in Room 204", "All building occupants").
- The criticalasset_update_draft should be a single short paragraph suitable for copy-pasting into a work order or CriticalAsset ticket.
- Return ONLY valid JSON matching the schema. No markdown, no preamble, no explanation.
"""

_USER_PROMPT_TEMPLATE = """\
Analyze the attached facility image submitted by a student or staff member at an NYC school.
{context_block}

Return ONLY this JSON structure — no markdown, no extra text:
{{
  "issue_type": "<short category, e.g. HVAC / Ventilation, Plumbing / Water, Electrical / Lighting, Structural / Safety, Pest / Sanitation, Mold / Air Quality, Elevator / Accessibility, Fire Safety / Sprinkler, or Unknown>",
  "visible_evidence": ["<list of specific things visible in the image that support the diagnosis>"],
  "likely_asset_or_system": "<specific asset or system involved, e.g. Unit Ventilator, Boiler, Ceiling Tile, Sprinkler Head>",
  "severity": "<low | medium | high>",
  "confidence_label": "<Verified | Likely | Inferred | Missing | Needs Inspection | Conflicting>",
  "affected_users": "<who is impacted and scope>",
  "missing_information": ["<list of information that would improve confidence or action, or empty list if none>"],
  "recommended_action": "<single most important next step for the facility team>",
  "criticalasset_update_draft": "<one-paragraph work order / CriticalAsset ticket draft>"
}}
"""

def _build_user_prompt(optional_context: str) -> str:
    if optional_context and optional_context.strip():
        context_block = f'Additional context provided by the reporter:\n"{optional_context.strip()}"'
    else:
        context_block = "No additional context was provided — base your analysis on the image alone."
    return _USER_PROMPT_TEMPLATE.format(context_block=context_block)


# ── Fallback parser ───────────────────────────────────────────────────────────

_FALLBACK_RESPONSE = {
    "issue_type":                "Unknown",
    "visible_evidence":          [],
    "likely_asset_or_system":    "Unknown",
    "severity":                  "medium",
    "confidence_label":          "Needs Inspection",
    "affected_users":            "Unknown — on-site verification required",
    "missing_information":       ["Image could not be analyzed", "Manual inspection required"],
    "recommended_action":        "Submit image to facilities coordinator for manual review.",
    "criticalasset_update_draft": (
        "Automated analysis was unable to parse a structured response from the submitted image. "
        "Please review the original photo manually and create a work order after on-site inspection."
    ),
}

def parse_or_fallback_response(response_text: str) -> dict:
    """
    Parse the model's JSON response. If parsing fails, return a safe fallback
    dict that still satisfies the output schema so the caller never crashes.
    """
    clean = response_text.strip()
    # Strip any accidental markdown fences
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.strip()

    try:
        parsed = json.loads(clean)
        # Ensure all required keys are present; fill missing ones from fallback
        for key, default in _FALLBACK_RESPONSE.items():
            if key not in parsed:
                parsed[key] = default
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[projectnyc_vision] JSON parse error: {e}\nRaw response: {response_text!r}")
        return dict(_FALLBACK_RESPONSE)


# ── Main analysis function ────────────────────────────────────────────────────

def analyze_signal_image(image_path: str, optional_context: str = "") -> dict:
    """
    Analyze a single facility image and return structured signal intelligence.

    Args:
        image_path:       Path to the uploaded image file.
        optional_context: Free-text note from the student/staff reporter (optional).

    Returns:
        dict matching the ProjectNYC output schema.
    """
    image_b64   = encode_image(image_path)
    user_prompt = _build_user_prompt(optional_context)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": _SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        max_tokens=600,
        temperature=0.2,   # low temperature = more consistent structured output
    )

    raw = response.choices[0].message.content
    return parse_or_fallback_response(raw)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python projectnyc_vision.py <image_path> [optional context text]")
        sys.exit(1)

    image_path       = sys.argv[1]
    optional_context = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""

    print(f"[projectnyc_vision] Analyzing: {image_path}")
    if optional_context:
        print(f"[projectnyc_vision] Context: {optional_context}")

    result = analyze_signal_image(image_path, optional_context)
    print(json.dumps(result, indent=2))
