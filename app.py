from flask import Flask, request, jsonify, render_template, send_from_directory
from urllib.parse import urlparse
import re
import math
import os
import tempfile

from werkzeug.utils import secure_filename

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    import pytesseract
except ImportError:
    pytesseract = None

app = Flask(__name__, template_folder="templates", static_folder="assets")

def url_signals(u):
    signals = []
    score = 0
    u = (u or "").strip()
    parsed = urlparse(u)
    host = parsed.hostname or ""
    path = parsed.path or ""
    if not host:
        signals.append({"sev":"high","title":"Invalid or incomplete URL","why":"A domain could not be parsed. Treat shortened or malformed links cautiously."})
        score += 25
        return score, signals, host

    lower = (host + " " + path).lower()
    if "xn--" in lower:
        score += 25
        signals.append({"sev":"high","title":"Punycode / look-alike risk","why":"Internationalized domain encoding can be used for visual impersonation."})
    if re.search(r"(rbi|reserve-bank|cibil|sbi|hdfc|icici|axis|paytm|phonepe|loan|instant|cash|credit)", host, re.I) and re.search(r"(free|fast|urgent|apply|verify|offer|support|secure|official|help)", host, re.I):
        score += 18
        signals.append({"sev":"medium","title":"Brand/loan keyword pressure","why":"The domain uses high-trust or urgency keywords; this is not proof of legitimacy."})
    if len(host) > 35:
        score += 12
        signals.append({"sev":"medium","title":"Unusually long domain","why":"Long domains can make impersonation and hidden subdomains harder to notice."})
    if not u.lower().startswith("https://"):
        score += 20
        signals.append({"sev":"high","title":"HTTPS not detected","why":"Sensitive loan information should not be submitted over an unencrypted HTTP connection."})
    if re.search(r"(free|100%|instant|guarantee|no.?cibil)", lower, re.I):
        score += 10
        signals.append({"sev":"medium","title":"High-pressure marketing language","why":"Promises such as instant/no-CIBIL/guaranteed approval deserve independent verification."})
    return min(100, score), signals, host

def message_signals(m):
    signals = []
    score = 0
    checks = [
        ("upfront payment", r"(pay|send|deposit|fee).{0,40}(processing|advance|unlock|release|security)", 28),
        ("urgency", r"(urgent|today|limited|last chance|immediately|within \d+ minutes)", 14),
        ("guaranteed approval", r"(guaranteed|100%|sure approval|no cibil|bad credit.*approved)", 18),
        ("credential request", r"(otp|pin|cvv|password|netbanking|upi pin)", 35),
        ("off-platform link", r"(bit\.ly|tinyurl|t\.co|wa\.me|telegram\.me)", 18),
        ("threatening recovery language", r"(contacts|photos|blackmail|police case|legal action|harass)", 20),
    ]
    for title, pattern, weight in checks:
        if re.search(pattern, m or "", re.I):
            score += weight
            signals.append({"sev":"high" if weight >= 25 else "medium",
                            "title":title.title(),
                            "why":"This pattern commonly increases the need for independent verification."})
    return min(100, score), signals

def extract_credit_report(file_storage):
    """Extract readable text from a user-supplied credit report locally."""
    if not file_storage or not file_storage.filename:
        return "", "No report file supplied", "none"

    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".csv"}
    if ext not in allowed:
        return "", "Unsupported file type", "none"

    raw = file_storage.read()
    if len(raw) > 15 * 1024 * 1024:
        return "", "File is larger than the 15 MB demo limit", "none"

    if ext in {".txt", ".csv"}:
        return raw.decode("utf-8", errors="replace"), "Text extracted locally", "text"

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(raw)
        temp_path = tmp.name

    try:
        if ext == ".pdf":
            if fitz is None:
                return "", "PDF extractor is not installed", "pdf"
            doc = fitz.open(temp_path)
            parts = []
            for page in doc:
                text = page.get_text("text") or ""
                if text.strip():
                    parts.append(text)
                elif pytesseract is not None and Image is not None:
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    parts.append(pytesseract.image_to_string(image))
            doc.close()
            return "\n".join(parts).strip(), "PDF text/OCR extracted locally", "pdf"

        if ext in {".png", ".jpg", ".jpeg", ".webp"}:
            if pytesseract is None or Image is None:
                return "", "Image OCR is not installed", "image"
            text = pytesseract.image_to_string(Image.open(temp_path))
            return text.strip(), "Image OCR extracted locally", "image"
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    return "", "Could not extract report text", "none"


def credit_report_signals(text):
    """Find common credit-report fields and obvious exposure anomalies."""
    t = text or ""
    low = t.lower()

    def first(pattern, default=0):
        m = re.search(pattern, low, re.I)
        return int(m.group(1)) if m else default

    active = first(r"(?:active|open)\s+(?:loan|account)s?\s*[:\-]?\s*(\d+)")
    if active == 0:
        active = first(r"(\d+)\s+(?:active|open)\s+(?:loan|account)s?")

    enquiries = first(r"(?:total\s+)?(?:credit\s+)?enquir(?:ies|y)\s*[:\-]?\s*(\d+)")
    unknown = first(r"(\d+)\s+(?:unknown|unrecognized|unrecognised)\s+(?:enquir(?:y|ies)|account)s?")
    if unknown == 0 and re.search(r"\b(?:unknown|unrecognized|unrecognised)\b", low):
        unknown = 1

    score_match = re.search(r"(?:cibil|credit)\s+score\s*[:\-]?\s*(\d{3})", low, re.I)
    score = int(score_match.group(1)) if score_match else None

    overdue = first(r"(?:overdue|past\s+due)\s*(?:amount)?\s*[:\-]?\s*[₹rs.\s]*([0-9,]+)", 0)
    overdue = int(str(overdue).replace(",", "")) if overdue else 0

    lender_matches = re.findall(r"(?:lender|bank|nbfc|institution)\s*[:\-]\s*([^\n,]{2,60})", t, re.I)
    lenders = []
    for x in lender_matches:
        x = re.sub(r"\s+", " ", x).strip()
        if x and x not in lenders:
            lenders.append(x)

    flags = []
    if unknown:
        flags.append({"sev":"high", "title":"Unknown account/enquiry detected", "why":"The extracted report contains an entry described as unknown or unrecognized. Verify it with the lender and bureau."})
    if overdue > 0:
        flags.append({"sev":"high", "title":"Overdue amount detected", "why":"The report text contains an overdue/past-due amount. Confirm the account status and amount."})
    if enquiries >= 5:
        flags.append({"sev":"medium", "title":"Multiple recent enquiries", "why":"The report shows a relatively high enquiry count; review whether each enquiry was authorized."})
    if not flags:
        flags.append({"sev":"low", "title":"No obvious exposure anomaly found", "why":"The demo parser did not detect the specific warning patterns it checks. This is not a bureau decision or proof that the report is error-free."})

    return {
        "active": active if active else "unknown",
        "unknown": unknown,
        "enquiries": enquiries if enquiries else "unknown",
        "score": score,
        "overdue": overdue,
        "lenders": lenders[:8],
        "flags": flags,
    }

def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api.php")
def api():
    action = request.form.get("action", "")
    if action == "scan":
        m = request.form.get("message", "")
        u = request.form.get("url", "")
        us, u_sig, host = url_signals(u)
        ms, m_sig = message_signals(m)
        signals = u_sig + m_sig
        score = min(100, us + ms)
        level = "HIGH" if score >= 65 else ("MEDIUM" if score >= 35 else "LOW")
        verdict = (
            "Pause and independently verify before paying or sharing data." if level == "HIGH"
            else "Proceed only after checking the lender relationship, KFS and domain." if level == "MEDIUM"
            else "No major demo heuristic triggered; this is not proof of safety."
        )
        return jsonify(ok=1, score=score, level=level, host=host, verdict=verdict,
            signals=signals,
            checks={
                "Regulatory association":"Needs independent verification",
                "Domain structure":"No major heuristic" if score < 35 else "Review required",
                "Loan terms":"Check KFS/APR/fees",
                "Permissions":"Only need-based, consented data",
                "Message patterns":"Red flags detected" if ms >= 20 else "No major red flag",
                "Evidence":"Preserve original message and URL"
            })

    if action == "url":
        score, signals, host = url_signals(request.form.get("url", ""))
        level = "HIGH" if score >= 65 else ("MEDIUM" if score >= 35 else "LOW")
        return jsonify(ok=1, score=score, level=level, host=host, signals=signals,
            official="If a lender claims RBI association, verify the relationship on the regulated entity’s own official website and the RBI public DLA repository.")

    if action == "fit":
        salary = max(0.0, num(request.form.get("salary")))
        existing = max(0.0, num(request.form.get("existing")))
        loan = max(0.0, num(request.form.get("loan")))
        try:
            months = max(1, int(float(request.form.get("months", 1))))
        except (TypeError, ValueError):
            months = 1
        rate = max(0.0, num(request.form.get("rate"))) / 1200
        expenses = max(0.0, num(request.form.get("expenses")))
        if rate:
            emi = loan * rate * ((1 + rate) ** months) / (((1 + rate) ** months) - 1)
        else:
            emi = loan / months
        ratio = (existing + emi) / salary if salary else 1
        head = salary - expenses - existing - emi
        score = max(0, min(100, round(100 - ratio * 100 - (20 if head < 0 else 0))))
        band = "Lower repayment pressure" if score >= 70 else ("Moderate repayment pressure" if score >= 45 else "High repayment pressure")
        return jsonify(ok=1, emi=round(emi), ratio=round(ratio * 100, 1), headroom=round(head), score=score, band=band)

    if action == "credit":
        summary = request.form.get("summary", "")
        uploaded = request.files.get("creditFile")
        extracted, extraction_note, source_type = extract_credit_report(uploaded) if uploaded else ("", "No file uploaded", "none")
        text = extracted if extracted.strip() else summary
        result = credit_report_signals(text)
        return jsonify(ok=1, **result, extraction_note=extraction_note, source_type=source_type,
            extracted_text=extracted[:30000],
            actions=[
                "Download your report only from the bureau’s official channel.",
                "Match every account and enquiry against your records.",
                "Contact the lender shown on an unfamiliar entry.",
                "Raise a dispute with the bureau if the information is inaccurate."
            ])

    return jsonify(ok=0, error="Unknown action")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
