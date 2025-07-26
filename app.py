from flask import Flask, render_template, request, jsonify
import os
import whisper
import sqlite3
import json
from openai import OpenAI
from datetime import datetime
import pandas as pd

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load Whisper model once
model = whisper.load_model("base")

# Transcription function
def transcribe_audio(filepath):
    result = model.transcribe(filepath)
    return result["text"]


def create_crm_table():
    conn = sqlite3.connect("dummy_crm.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crm_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            clinic_name TEXT,
            date DATE,
            contact_prefix TEXT,
            contact_surname TEXT,
            contact_first_name TEXT,
            product TEXT,
            quantity INTEGER,
            shipping_address TEXT,
            eircode TEXT,
            interest_type TEXT,
            remarks TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def insert_crm_order(data):
    conn = sqlite3.connect("dummy_crm.db")
    cursor = conn.cursor()

    from datetime import datetime
    raw_date = data.get("date", "")
    try:
        formatted_date = datetime.strptime(raw_date, "%d/%m/%Y").strftime("%Y-%m-%d")
    except:
        formatted_date = raw_date  # fallback
    
    cursor.execute("""
        INSERT INTO crm_orders (
            employee_id, clinic_name, date,
            contact_prefix, contact_surname, contact_first_name,
            product, quantity, shipping_address, eircode,
            interest_type, remarks
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("employee_id", ""),
        data.get("clinic_name", ""),
        formatted_date,  
        data.get("contact_prefix", ""),
        data.get("contact_surname", ""),
        data.get("contact_first_name", ""),
        data.get("product", ""),
        data.get("quantity", 0),
        data.get("shipping_address", ""),
        data.get("eircode", ""),
        data.get("interest_type", ""),
        data.get("remarks", "")
    ))
    conn.commit()
    conn.close()


def extract_requests_from_text(text):
    from openai import OpenAI
    import json

    # Initialize DeepSeek API client
    client = OpenAI(
        api_key="sk-4e8d9210119f44818082924d3ecf63f7",  
        base_url="https://api.deepseek.com"
    )

    # Prompt for the model to extract all required CRM fields from the transcript
    prompt = f"""
    You are a CRM assistant. Extract **all individual requests** from the following transcript of a sales voice note. 
    Return a JSON array of objects. Each object must contain the following fields:

    - employee_id
    - clinic_name
    - date
    - contact_prefix
    - contact_surname
    - contact_first_name
    - product
    - quantity
    - shipping_address
    - eircode
    - interest_type (choose from ["new order", "restock", "complaint", "sample request", "others"])
    - remarks (any extra notes or complaint details)

    If some fields are not mentioned in the transcript, leave them as null or empty string.
    Do not include any explanation or markdown. Only return raw JSON array.

    ---
    Transcript:
    \"\"\"{text}\"\"\"
    """

    # Call the DeepSeek chat completion API
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    # Get the raw response text
    reply = response.choices[0].message.content.strip()

    # Remove markdown formatting if present (e.g., ```json ... ```)
    if "```json" in reply:
        reply = reply.split("```json")[1].split("```")[0].strip()

    try:
        # Parse JSON string into Python list of dicts
        requests = json.loads(reply)
        return requests
    except Exception as e:
        # Raise a helpful error if parsing fails
        raise ValueError(f"❌ JSON parsing error: {e}\nRaw reply:\n{reply}")

def get_clinic_suggestions(clinic_name):
    client = OpenAI(
        api_key="sk-4e8d9210119f44818082924d3ecf63f7", 
        base_url="https://api.deepseek.com"
    )

    conn = sqlite3.connect("dummy_crm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT clinic_name FROM crm_orders")
    existing_clinics = [row[0] for row in cursor.fetchall()]
    conn.close()

    example_list = "\n".join(f"- {name}" for name in existing_clinics[:100])

    prompt = f"""
    Given a new clinic name input: "{clinic_name}", find up to 3 most semantically similar clinic names from the list below.
    Return them in a JSON list. If there are no close matches, return an empty list.

    Clinic name list:
    {example_list}
    """

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    reply = response.choices[0].message.content.strip()

    if "```json" in reply:
        reply = reply.split("```json")[1].split("```")[0].strip()

    try:
        suggestions = json.loads(reply)
        return suggestions if isinstance(suggestions, list) else []
    except Exception:
        return []
    

def get_contact_suggestions(prefix, first_name, surname, clinic_name=None):
    import json
    from openai import OpenAI

    parts = [prefix, first_name, surname]
    full_input = " ".join(p for p in parts if p and p.strip()).strip()
    if not full_input:
        return []

    conn = sqlite3.connect("dummy_crm.db")
    cursor = conn.cursor()
    if clinic_name:
        cursor.execute("""
            SELECT DISTINCT contact_prefix, contact_first_name, contact_surname 
            FROM crm_orders 
            WHERE clinic_name = ?
        """, (clinic_name,))
    else:
        cursor.execute("SELECT DISTINCT contact_prefix, contact_first_name, contact_surname FROM crm_orders")
    rows = cursor.fetchall()
    conn.close()


    contact_list = [
        " ".join(part for part in [p, f, s] if part and str(part).strip()).strip()
        for p, f, s in rows if any([p, f, s])
    ]
    if not contact_list:
        return []

    client = OpenAI(
        api_key="sk-4e8d9210119f44818082924d3ecf63f7",
        base_url="https://api.deepseek.com"
    )

    examples = "\n".join(f"- {c}" for c in contact_list[:100])

    prompt = f"""
    Given a new contact: "{full_input}", find up to 3 semantically similar contacts from the list below.
    Each contact is a full name with title. Return a JSON list. If no match, return an empty list.

    Contact list:
    {examples}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        reply = response.choices[0].message.content.strip()
        if "```json" in reply:
            reply = reply.split("```json")[1].split("```")[0].strip()

        suggestions = json.loads(reply)
        return suggestions if isinstance(suggestions, list) else []
    except Exception as e:
        print("❌ get_contact_suggestions error:", str(e))
        return []





@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("audio")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Step 1: Save the uploaded audio file
    filename = file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # Step 2: Transcribe the audio using Whisper
    transcript = transcribe_audio(filepath)

    # Step 3: Extract structured CRM requests using DeepSeek
    try:
        requests = extract_requests_from_text(transcript)
        requests = [r for r in requests if isinstance(r, dict)]
    except Exception as e:
        return jsonify({"error": f"Failed to extract data: {str(e)}"}), 500

    results = []
    for req in requests:
        clinic_name = (req.get("clinic_name") or "").strip()
        prefix = (req.get("contact_prefix") or "").strip()
        first_name = (req.get("contact_first_name") or "").strip()
        surname = (req.get("contact_surname") or "").strip()

        # -------- Step 3.1: Clinic Matching --------
        clinic_suggestions = get_clinic_suggestions(clinic_name)
        with sqlite3.connect("dummy_crm.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM crm_orders WHERE clinic_name = ?", (clinic_name,))
            clinic_exists = cursor.fetchone()
        clinic_matched = bool(clinic_exists)

        # -------- Step 3.2: Contact Matching --------
        input_parts = [prefix, first_name, surname]
        input_full = " ".join(p for p in input_parts if p and str(p).strip()).strip().lower()

        with sqlite3.connect("dummy_crm.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT contact_prefix, contact_first_name, contact_surname
                FROM crm_orders
                WHERE clinic_name = ?
            """, (clinic_name,))
            db_contacts = cursor.fetchall()

        contact_matched = False
        for p, f, s in db_contacts:
            db_name = " ".join(part for part in [p, f, s] if part and str(part).strip()).strip().lower()
            if db_name == input_full:
                contact_matched = True
                break

        # -------- Step 3.3: Auto-fill shipping_address and eircode if missing --------
        if clinic_matched:
            shipping_blank = not req.get("shipping_address")
            eircode_blank = not req.get("eircode")
            if shipping_blank or eircode_blank:
                with sqlite3.connect("dummy_crm.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT shipping_address, eircode
                        FROM crm_orders
                        WHERE clinic_name = ?
                        AND (shipping_address IS NOT NULL OR eircode IS NOT NULL)
                        ORDER BY last_updated DESC
                        LIMIT 1
                    """, (clinic_name,))
                    row = cursor.fetchone()
                    if row:
                        historical_address, historical_eircode = row
                        if shipping_blank:
                            req["shipping_address"] = historical_address or ""
                        if eircode_blank:
                            req["eircode"] = historical_eircode or ""

        # -------- Step 3.4: Suggestion if contact not matched --------
        if not contact_matched:
            contact_suggestions = get_contact_suggestions(prefix, first_name, surname, clinic_name)
        else:
            contact_suggestions = []

        # -------- Final Result for This Record --------
        results.append({
            "data": req,
            "clinic_matched": clinic_matched,
            "clinic_suggestions": clinic_suggestions,
            "contact_matched": contact_matched,
            "contact_suggestions": contact_suggestions
        })

    # Step 4: Return transcript and enriched request data
    return jsonify({
        "transcript": transcript,
        "results": results
    })



@app.route("/get_contact_match_status", methods=["POST"])
def get_contact_match_status():
    data = request.get_json()
    prefix = (data.get("contact_prefix") or "").strip()
    first_name = (data.get("contact_first_name") or "").strip()
    surname = (data.get("contact_surname") or "").strip()
    clinic_name = (data.get("clinic_name") or "").strip()

    input_parts = [prefix, first_name, surname]
    input_full = " ".join(p for p in input_parts if p and p.strip()).strip().lower()

    if clinic_name.lower() in ["not listed above", ""]:
        return jsonify({
            "contact_matched": False,
            "contacts": [],
            "skip_contact_matching": True
        })

    with sqlite3.connect("dummy_crm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT contact_prefix, contact_first_name, contact_surname
            FROM crm_orders
            WHERE clinic_name = ?
        """, (clinic_name,))
        db_contacts = cursor.fetchall()

    contact_matched = False
    suggestions = []
    for p, f, s in db_contacts:
        db_full = " ".join(part for part in [p, f, s] if part and str(part).strip()).strip().lower()
        if db_full == input_full:
            contact_matched = True
            break
        else:
            suggestions.append(" ".join(part for part in [p, f, s] if part and str(part).strip()))

    return jsonify({
        "contact_matched": contact_matched,
        "contacts": suggestions,
        "skip_contact_matching": False
    })

@app.route("/get_address_by_clinic", methods=["POST"])
def get_address_by_clinic():
    data = request.get_json()
    clinic_name = data.get("clinic_name", "").strip()
    with sqlite3.connect("dummy_crm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT shipping_address, eircode
            FROM crm_orders
            WHERE clinic_name = ?
            AND (shipping_address IS NOT NULL OR eircode IS NOT NULL)
            ORDER BY last_updated DESC
            LIMIT 1
        """, (clinic_name,))
        row = cursor.fetchone()

    return jsonify({
        "shipping_address": row[0] if row else None,
        "eircode": row[1] if row else None
    })



@app.route("/confirm", methods=["POST"])
def confirm():
    try:
        data = request.get_json()
        confirmed_list = data.get("requests", [])
        for record in confirmed_list:
            insert_crm_order(record)
        return jsonify({
            "success": True,
            "message": f"{len(confirmed_list)} record(s) saved to database."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    create_crm_table()
    app.run(debug=True)
