"""
app.py
------
Flask backend for ProjectNYC Signal Intelligence.
Serves index.html and exposes three API routes.
"""

import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder=".")


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/workorders")
def api_workorders():
    from criticalasset_client import get_access_token, fetch_work_orders

    token_data = get_access_token()
    result = fetch_work_orders(limit=25, token=token_data["accessToken"])
    return jsonify(result.get("workOrders", {"nodes": [], "totalCount": 0}))


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    from ai_enrichment import enrich_text_signal
    from nyc_data import get_public_context

    description = request.form.get("description", "").strip()
    issue_type = request.form.get("issue_type", "").strip()

    context = description
    if issue_type and issue_type not in ("auto", ""):
        context = f"Issue type hint: {issue_type}\n\n{context}"

    has_image = "image" in request.files and request.files["image"].filename

    if has_image:
        from projectnyc_vision import analyze_signal_image

        img = request.files["image"]
        suffix = os.path.splitext(img.filename or "")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            img.save(f.name)
            tmp_path = f.name
        try:
            result = analyze_signal_image(tmp_path, context)
        finally:
            os.unlink(tmp_path)
    else:
        if not context:
            return jsonify({"error": "No description or image provided"}), 400
        result = enrich_text_signal(context)

    detected_type = result.get("issue_type", issue_type or "")
    result["public_data"] = get_public_context("90 Trinity Place", detected_type)
    return jsonify(result)


@app.route("/api/enrich-workorder", methods=["POST"])
def api_enrich_workorder():
    from ai_enrichment import enrich_work_order
    from nyc_data import get_public_context

    wo = request.get_json(force=True)
    result = enrich_work_order(wo)
    loc_name = (wo.get("location") or {}).get("locationName", "90 Trinity Place")
    result["public_data"] = get_public_context(loc_name, result.get("issue_type", ""))
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port)
