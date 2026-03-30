"""
SACDS v6 — Flask REST API
Run: python app.py
"""

from flask import Flask, request, jsonify, render_template
from sacds.engine import (
    analyze_document, get_all_users, get_policies,
    get_sensitivity_levels, USER_PERSONAS, DEFAULT_POLICIES
)
import traceback

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["JSON_SORT_KEYS"] = False


# ─── Frontend ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ─── REST API ─────────────────────────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
def api_users():
    """Return all user personas with role + clearance."""
    users = get_all_users()
    return jsonify({"users": users})


@app.route("/api/policies", methods=["GET"])
def api_policies():
    """Return role → policy mappings."""
    return jsonify({"policies": get_policies()})


@app.route("/api/sensitivity-levels", methods=["GET"])
def api_sensitivity():
    return jsonify({"levels": get_sensitivity_levels()})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Analyze a document through the SACDS pipeline.

    Request JSON:
      {
        "text":      "<document text>",
        "user_id":   "carol_employee",
        "doc_class": "internal",        // public|internal|confidential|restricted|secret
        "nlp_mode":  "hybrid"           // keyword_only|ner|hybrid
      }
    """
    body = request.get_json(silent=True) or {}
    text      = body.get("text", "").strip()
    user_id   = body.get("user_id",   "carol_employee")
    doc_class = body.get("doc_class", "internal")
    nlp_mode  = body.get("nlp_mode",  "hybrid")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    valid_users = list(USER_PERSONAS.keys())
    if user_id not in valid_users:
        return jsonify({"error": f"Unknown user_id. Valid: {valid_users}"}), 400

    valid_classes = ["public", "internal", "confidential", "restricted", "secret"]
    if doc_class not in valid_classes:
        return jsonify({"error": f"Invalid doc_class. Valid: {valid_classes}"}), 400

    try:
        result = analyze_document(text, user_id, doc_class, nlp_mode)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/extract-text", methods=["POST"])
def api_extract_text():
    """Extract text from an uploaded document (PDF, DOCX, TXT)."""
    if 'document' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['document']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    
    try:
        text = ""
        if ext == 'txt':
            text = file.read().decode('utf-8', errors='replace')
        elif ext == 'pdf':
            import pypdf
            reader = pypdf.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif ext in ['docx', 'doc']:
            import docx
            doc = docx.Document(file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            return jsonify({"error": f"Unsupported file format: {ext}"}), 400
            
        return jsonify({"text": text.strip()})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to parse document: {str(e)}"}), 500


@app.route("/api/sample-texts", methods=["GET"])
def api_sample_texts():
    """Return sample documents for quick testing."""
    samples = [
        {
            "label": "Mixed Sensitivity Report",
            "text": (
                "QUARTERLY BUSINESS REVIEW — Q3 2024\n\n"
                "This document is for internal distribution only.\n\n"
                "Market Performance\n"
                "Our product line achieved strong market penetration this quarter. "
                "Total revenue reached $4.2 million USD, representing a 14% increase year-over-year. "
                "EBITDA margin improved to 22%, driven by cost optimisation initiatives.\n\n"
                "Personnel Update\n"
                "Employee John Smith (SSN: 123-45-6789) has been promoted to Senior Manager. "
                "His new salary of $120,000 takes effect from November 1st. "
                "Contact: john.smith@company.com | Phone: (555) 867-5309\n\n"
                "Legal Notice\n"
                "This report is subject to attorney-client privilege. "
                "The pending litigation with Acme Corp regarding patent infringement "
                "is covered under NDA clause 7.3. Counsel advises no public disclosure.\n\n"
                "Public Announcement\n"
                "We are pleased to announce our new partnership with GlobalTech. "
                "A press release will be issued on December 1st for immediate release."
            ),
        },
        {
            "label": "Classified Intelligence Brief",
            "text": (
                "CLASSIFICATION: TOP SECRET — EYES ONLY\n\n"
                "This document contains special access program information. "
                "Compartmented intelligence — NOFORN. National security implications apply.\n\n"
                "The subject identified as A. Johnson, DOB: 05/12/1978, Passport: B12345678 "
                "was observed at coordinates 28.6139° N, 77.2090° E on 14 Oct 2024.\n\n"
                "Counterparty has initiated legal proceedings. "
                "Settlement negotiations are covered under litigation privilege."
            ),
        },
        {
            "label": "Public Press Release",
            "text": (
                "FOR IMMEDIATE RELEASE\n\n"
                "ACME Corporation Announces New Open Source Initiative\n\n"
                "Acme Corporation today announced the launch of its open source developer toolkit, "
                "available to all registered customers via our public portal. "
                "The toolkit includes comprehensive documentation and publicly available APIs.\n\n"
                "About Acme Corporation\n"
                "Founded in 1995, Acme Corporation is a global leader in enterprise software. "
                "For more information, visit www.acme.com or contact press@acme.com."
            ),
        },
    ]
    return jsonify({"samples": samples})


if __name__ == "__main__":
    print("🛡️  SACDS v6 — Starting server on http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
