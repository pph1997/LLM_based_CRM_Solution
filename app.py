# # --- Imports ---
# import sqlite3
# import whisper
# import google.generativeai as genai
# import json
# import os

# # Point to your ffmpeg bin directory

# # --- CONFIGURE GEMINI ---
# genai.configure(api_key="xxxx")
# model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest")

# ffmpeg_path = r"D:\Brother\ffmpeg\bin"
# os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ["PATH"]

# # --- STEP 1: Transcribe Voice Note ---
# def transcribe_audio():
#     model = whisper.load_model("base")
#     result = model.transcribe(r"D:\Brother\Sample_Prompt.m4a")
#     return result['text']
# transcript = transcribe_audio()
# print("Transcript:\n", transcript)

# # --- STEP 2: Extract Fields Using Gemini ---
# def extract_crm_fields_gemini(text):
#     prompt = f"""
#     Extract the following fields from the transcript of a sales voice note and return them in JSON:
#     - employee_id
#     - clinic_name
#     - date
#     - contact_prefix
#     - contact_surname
#     - contact_first_name
#     - product
#     - quantity
#     - shipping_address
#     - eircode

#     Transcript:
#     \"\"\"{text}\"\"\"
#     """

#     response = model.generate_content(prompt)
#   # Show the raw response for debugging
#     print("🔍 Gemini raw response:\n", response.text)

#     # Clean the response (remove triple backticks and json label)
#     cleaned_text = (
#         response.text.replace("```json", "")
#         .replace("```", "")
#         .strip()
#     )

#     return json.loads(cleaned_text)

# # --- STEP 3: Create Database ---
# def create_crm_table():
#     conn = sqlite3.connect("dummy_crm.db")
#     cursor = conn.cursor()
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS crm_orders (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         employee_id TEXT,
#         clinic_name TEXT,
#         date TEXT,
#         contact_prefix TEXT,
#         contact_surname TEXT,
#         contact_first_name TEXT,
#         product TEXT,
#         quantity INTEGER,
#         shipping_address TEXT,
#         eircode TEXT,
#         last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
#     """)
#     conn.commit()
#     conn.close()
#     print("CRM table ready.")


# # --- STEP 4: Insert Data into Database ---
# def insert_crm_data(data):
#     conn = sqlite3.connect("dummy_crm.db")
#     cursor = conn.cursor()
#     cursor.execute("""
#     INSERT INTO crm_orders (
#         employee_id, clinic_name, date, contact_prefix, contact_surname,
#         contact_first_name, product, quantity, shipping_address, eircode
#     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#     """, (
#         data['employee_id'], data['clinic_name'], data['date'],
#         data['contact_prefix'], data['contact_surname'], data['contact_first_name'],
#         data['product'], data['quantity'], data['shipping_address'], data['eircode']
#     ))
#     conn.commit()
#     conn.close()
#     print("Data inserted into CRM database.")

# if __name__ == "__main__":
#     create_crm_table()
#     transcript = transcribe_audio()
#     print("🎤 Transcript:\n", transcript)

#     crm_data = extract_crm_fields_gemini(transcript)
#     insert_crm_data(crm_data)


from flask import Flask, request, jsonify, render_template
import sqlite3
import whisper
import google.generativeai as genai
import json
import os

app = Flask(__name__)

# --- CONFIGURE GEMINI ---
genai.configure(api_key="AIzaSyCudgD8b3DQHHhoQ48U7Z1e7-BbWtc2ULg")
gemini_model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest")

ffmpeg_path = r"C:\Patrick's Documents\Learning\TCD\Dissertation\ffmpeg-2025-05-15-git-12b853530a-essentials_build\bin"
os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ["PATH"]

# --- DATABASE SETUP ---
def create_crm_table():
    conn = sqlite3.connect("dummy_crm.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crm_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT,
        clinic_name TEXT,
        date TEXT,
        contact_prefix TEXT,
        contact_surname TEXT,
        contact_first_name TEXT,
        product TEXT,
        quantity INTEGER,
        shipping_address TEXT,
        eircode TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

def insert_crm_data(data):
    conn = sqlite3.connect("dummy_crm.db")
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO crm_orders (
        employee_id, clinic_name, date, contact_prefix, contact_surname,
        contact_first_name, product, quantity, shipping_address, eircode
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['employee_id'], data['clinic_name'], data['date'],
        data['contact_prefix'], data['contact_surname'], data['contact_first_name'],
        data['product'], data['quantity'], data['shipping_address'], data['eircode']
    ))
    conn.commit()
    conn.close()

# --- WHISPER + GEMINI PIPELINE ---
def transcribe_audio(filepath):
    model = whisper.load_model("base")
    result = model.transcribe(filepath)
    return result['text']

def extract_crm_fields_gemini(text):
    prompt = f"""
    Extract the following fields from the transcript of a sales voice note and return them in JSON:
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

    Transcript:
    \"\"\"{text}\"\"\"
    """
    response = gemini_model.generate_content(prompt)
    cleaned = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)

# --- ROUTES ---
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["audio"]
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filepath = os.path.join("uploads", file.filename)
    file.save(filepath)

    transcript = transcribe_audio(filepath)
    crm_data = extract_crm_fields_gemini(transcript)
    insert_crm_data(crm_data)

    return jsonify({"message": "Uploaded and processed", "transcript": transcript, "data": crm_data})

# --- START ---
if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    create_crm_table()
    port = int(os.environ.get("PORT", 10000))  # Render provides this PORT
    app.run(host='0.0.0.0', port=port)
