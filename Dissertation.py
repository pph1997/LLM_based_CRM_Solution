
# --- Imports ---
import sqlite3
import whisper
import google.generativeai as genai
import json
import os

# --- CONFIGURE GEMINI ---
genai.configure(api_key="AIzaSyCudgD8b3DQHHhoQ48U7Z1e7-BbWtc2ULg")
model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest")

ffmpeg_path = r"C:\Patrick's Documents\Learning\TCD\Dissertation\ffmpeg-2025-05-15-git-12b853530a-essentials_build\ffmpeg-2025-05-15-git-12b853530a-essentials_build\bin"
os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ["PATH"]

# --- STEP 1: Transcribe Voice Note ---
def transcribe_audio():
    model = whisper.load_model("base")
    result = model.transcribe("C:\Patrick's Documents\Learning\TCD\Dissertation\Sample_Prompt.m4a")
    return result['text']
transcript = transcribe_audio()
print("Transcript:\n", transcript)

# --- STEP 2: Extract Fields Using Gemini ---
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

    response = model.generate_content(prompt)
  # Show the raw response for debugging
    print("🔍 Gemini raw response:\n", response.text)

    # Clean the response (remove triple backticks and json label)
    cleaned_text = (
        response.text.replace("```json", "")
        .replace("```", "")
        .strip()
    )

    return json.loads(cleaned_text)

# --- STEP 3: Create Database ---
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
    print("CRM table ready.")


# --- STEP 4: Insert Data into Database ---
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
    print("Data inserted into CRM database.")

# --- Main Execution ---
# Extract fields
extracted_data = extract_crm_fields_gemini(transcript)
print("Extracted Data:\n", extracted_data)

# Create the table if it doesn't exist
create_crm_table()
# Insert into DB
insert_crm_data(extracted_data)

# View inserted data
def view_all_records():
    conn = sqlite3.connect("dummy_crm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crm_orders")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()

view_all_records()