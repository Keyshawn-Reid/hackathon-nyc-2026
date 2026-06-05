"""
nyc_data.py
-----------
Pulls public violation and complaint records from NYC Open Data to enrich work orders.
Translates raw records into operational meaning — not just links or counts.
"""

import requests

_TIMEOUT = 8

# Issue-type compliance context (used when live records are sparse)
_COMPLIANCE = {
    "HVAC / Ventilation": (
        "NYC Admin Code §27-2029 requires building owners to maintain heating between 68°F–76°F "
        "during occupied hours (Oct 1–May 31). Ventilation deficiencies may trigger DOHMH or DOB "
        "inspection. IAQ complaints can be filed with DOE or 311 under 'Unsatisfactory Temperature'."
    ),
    "Plumbing / Water": (
        "NYC Plumbing Code requires licensed plumbers for most repairs. Floor drain backups and sewer "
        "gas intrusion can indicate a failed trap primer or blocked sanitary line — both are Class B "
        "violations if not remedied within 30 days of notice. Notify building engineer immediately "
        "if water is spreading near electrical panels."
    ),
    "Electrical / Lighting": (
        "NYC Electrical Code requires all work be performed by a licensed electrician. Exposed wiring, "
        "water near panels, or recurring outages are potential fire safety violations subject to FDNY "
        "or DOB inspection. Log the outage location and timestamp for the insurance/compliance record."
    ),
    "Fire Safety / Sprinkler": (
        "NYC FC §901.6 requires annual sprinkler inspections. Blocked egress, failed exit signs, and "
        "malfunctioning sprinkler heads are Class 1 life-safety violations. FDNY can issue an "
        "immediately hazardous (IH) violation requiring same-day remediation. Do not close this "
        "work order without documented inspection by a licensed fire suppression contractor."
    ),
    "Elevator / Accessibility": (
        "NYC DOB requires annual elevator inspections. Out-of-service elevators in buildings with "
        "ADA obligations must have an accessible alternative documented. Report to DOB Elevator "
        "Division if the elevator is unsafe; NYC LL152 may also apply for gas-related concerns."
    ),
    "Structural / Safety": (
        "NYC Admin Code §28-301.1 places the obligation for safe maintenance on the building owner. "
        "Ceiling collapses, falling material, or structural cracks are Class 1 DOB violations. "
        "File a complaint at DOB NOW if the issue poses an imminent hazard."
    ),
    "Mold / Air Quality": (
        "NYC Local Law 55 (2018) requires building owners to remediate mold in rental dwellings. "
        "In schools, the NYC DOE requires mold remediation protocols per NYC DOHMH guidelines. "
        "Affected area >10 sq ft requires a licensed mold remediation contractor."
    ),
    "Pest / Sanitation": (
        "NYC Health Code §Art. 151 requires building owners to exterminate pests within 30 days. "
        "In school settings, the NYC DOE Integrated Pest Management (IPM) policy governs treatment. "
        "File with DOHMH or 311 under 'Rodent' or 'Cockroach' to create a public record."
    ),
}


def _dob_violations(boro: str = "1", block: str = "", lot: str = "") -> list:
    url = "https://data.cityofnewyork.us/resource/3h2n-5cm9.json"
    params = {"$limit": 10, "$order": "issuedate DESC"}
    if block and lot:
        params["$where"] = f"boro='{boro}' AND block='{block}' AND lot='{lot}'"
    else:
        params["$where"] = "housenumber='90' AND streetname='TRINITY PLACE' AND boro='1'"
    try:
        r = requests.get(url, params=params, timeout=_TIMEOUT)
        return r.json() if r.ok and isinstance(r.json(), list) else []
    except Exception:
        return []


def _complaints_311(address: str = "90 TRINITY PLACE") -> list:
    url = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
    params = {
        "$where": f"incident_address='{address.upper()}'",
        "$limit": 10,
        "$order": "created_date DESC",
    }
    try:
        r = requests.get(url, params=params, timeout=_TIMEOUT)
        return r.json() if r.ok and isinstance(r.json(), list) else []
    except Exception:
        return []


def _summarize_violations(records: list) -> str:
    if not records:
        return "No active DOB violations found for this address in public records."
    count = len(records)
    recent = records[:3]
    types = list({r.get("violation_category", r.get("violation_type_code", "")) for r in recent if r.get("violation_category") or r.get("violation_type_code")})
    summary = f"{count} DOB violation record(s) found."
    if types:
        summary += f" Categories include: {', '.join(types[:3])}."
    summary += " Review these records before closing any life-safety work order."
    return summary


def _summarize_complaints(records: list, issue_type: str = "") -> str:
    if not records:
        return "No recent 311 complaints found for this address."
    count = len(records)
    ctypes = list({r.get("complaint_type", "") for r in records if r.get("complaint_type")})
    summary = f"{count} recent 311 complaint(s) logged at this address."
    if ctypes:
        summary += f" Complaint types: {', '.join(ctypes[:4])}."
    summary += " Cross-reference with open work orders to identify recurring patterns."
    return summary


def get_public_context(location: str = "90 Trinity Place", issue_type: str = "") -> dict:
    violations = _dob_violations()
    complaints = _complaints_311()

    compliance_note = _COMPLIANCE.get(issue_type, "")
    if not compliance_note:
        # Try partial match
        for key in _COMPLIANCE:
            if any(word in issue_type for word in key.split(" / ")):
                compliance_note = _COMPLIANCE[key]
                break

    return {
        "dob_violations": violations[:5],
        "complaints_311": complaints[:5],
        "violation_summary": _summarize_violations(violations),
        "complaint_summary": _summarize_complaints(complaints, issue_type),
        "compliance_note": compliance_note,
        "has_public_records": bool(violations or complaints),
        "record_count": len(violations) + len(complaints),
    }
