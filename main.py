from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, make_response, jsonify
from pymongo import MongoClient
import io
from bson.objectid import ObjectId
import pytesseract
import base64
from PIL import Image
import os
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from pytesseract import TesseractError
from bcrypt import hashpw, checkpw, gensalt
import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import os
import pytesseract
import platform

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

load_dotenv()  # 🔥 this loads variables from .env into environment

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"), tls=True)
db = client['tos_app']
users_collection = db['users']
analysis_history_collection = db['analysis_history']

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

@app.route("/", methods=['GET', 'POST'])
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    history_id = request.args.get('history_id') or request.form.get('history_id')
    user_history = list(analysis_history_collection.find({'username': username}).sort('timestamp', -1).limit(10))

    if request.method == 'POST':
        text = request.form.get('text')
        file = request.files.get('file')
        filename, file_content = None, None

        if file and file.filename:
            filepath = os.path.join('uploads', file.filename)
            file.save(filepath)
            filename = file.filename
            if filepath.lower().endswith(('.png', '.jpg', '.jpeg')):
                try:
                    text = ocr_text(filepath)
                except Exception as e:
                    return render_template('error.html', error=str(e))
            else:
                try:
                    with open(filepath, 'r') as f:
                        file_content = f.read()
                        text = file_content
                        file_content = base64.b64encode(file_content.encode()).decode()
                except Exception as e:
                    return render_template('error.html', error=str(e))

        summary = summarize_text(text) if text else "No text provided."
        risks = highlight_risks(summary)

        analysis_data = {
            "username": username,
            "timestamp": datetime.datetime.now(),
            "filename": filename,
            "file_content": file_content,
            "input_text": text,
            "summary": summary,
            "risks": risks
        }

        if history_id:
            analysis_history_collection.update_one(
              {"_id": ObjectId(history_id), "username": username},
              {"$set": analysis_data}
            )
            
            flash("Analysis updated.", "success")
        else:
            analysis_history_collection.insert_one(analysis_data)
            flash("Analysis saved.", "success")

        user_history = list(analysis_history_collection.find({'username': username}).sort('timestamp', -1).limit(10))
        return redirect(url_for('dashboard', history_id=history_id) if history_id else url_for('dashboard'))

    if history_id:
        entry = analysis_history_collection.find_one({"_id": ObjectId(history_id), "username": username})
        if entry:
            return render_template("dashboard.html", username=username, summary=entry['summary'], risks=entry['risks'], input_text=entry['input_text'], history=user_history)

    return render_template("dashboard.html", username=username, summary=None, risks=None, history=user_history)

@app.route('/api/delete_entry/<history_id>', methods=['DELETE'])
def delete_entry(history_id):
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 403
    result = analysis_history_collection.delete_one({'_id': ObjectId(history_id), 'username': session['username']})
    if result.deleted_count == 1:
        return jsonify({"message": "Entry deleted successfully."}), 200
    return jsonify({"error": "Entry not found or unauthorized."}), 404

@app.route('/download_file/<history_id>')
def download_file(history_id):
    history_entry = analysis_history_collection.find_one({'_id': ObjectId(history_id)})
    if not history_entry or 'file_content' not in history_entry or 'filename' not in history_entry:
        flash('File not found.', 'error')
        return redirect(url_for('dashboard'))
    file_content = history_entry['file_content']
    filename = history_entry['filename']
    decoded_file_content = base64.b64decode(file_content.encode('utf-8'))
    return send_file(io.BytesIO(decoded_file_content), download_name=filename, as_attachment=True)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if users_collection.find_one({'username': username}):
            flash('Username already exists. Please choose a different one.')
            return render_template('register.html')
        hashed_password = hashpw(password.encode('utf-8'), gensalt())
        users_collection.insert_one({'username': username, 'password': hashed_password})
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username})
        if user and checkpw(password.encode('utf-8'), user['password']):
            session['username'] = username
            flash('Login successful.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out", 'success')
    return redirect(url_for('login'))

@app.route("/process")
def process():
    filepath = request.args.get('filepath')
    text = request.args.get('text')
    if text:
        summary = summarize_text(text)
        risks = highlight_risks(summary)
    elif filepath:
        if filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
            try:
                text = ocr_text(filepath)
            except TesseractError as e:
                return render_template('error.html', error=str(e))
            except FileNotFoundError:
                return render_template('error.html', error=f"Image file not found at path: {filepath}")
            except Exception as e:
                return render_template('error.html', error=str(e))
        else:
            try:
                with open(filepath, "r") as f:
                    text = f.read()
            except (UnicodeDecodeError, FileNotFoundError) as e:
                return render_template("error.html", error=str(e))
        summary = summarize_text(text) if text else "No text to process."
        risks = highlight_risks(text) if text else []
    else:
        summary = "No text to process."
        risks = []
    return render_template("results.html", summary=summary, risks=risks)

@app.route('/api/update_entry/<history_id>', methods=['PUT'])
def update_entry(history_id):
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    required_fields = ["input_text", "summary", "risks"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    update_data = {
        "input_text": data["input_text"],
        "summary": data["summary"],
        "risks": data["risks"],
        "timestamp": datetime.datetime.now()
    }

    if "filename" in data:
        update_data["filename"] = data["filename"]
    if "file_content" in data:
        update_data["file_content"] = data["file_content"]

    result = analysis_history_collection.update_one(
        {"_id": ObjectId(history_id), "username": session["username"]},
        {"$set": update_data}
    )

    if result.matched_count == 1:
        return jsonify({"message": "Entry updated successfully."}), 200
    return jsonify({"error": "Entry not found or unauthorized."}), 404

@app.route("/results")
def results():
    return redirect(url_for("index"))

def ocr_text(image_path):
    try:
        img = Image.open(image_path)
        # Enhance OCR accuracy
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img, lang='eng', config=custom_config)
        print("🔍 OCR Output:", text)  # Debug output in console
        return text.strip()
    except Exception as e:
        print("❌ OCR Error:", e)
        return "OCR failed."

def summarize_text(text):
    try:
        response = model.generate_content(f"Summarize the following text: {text}")
        return response.text
    except Exception as e:
        return f"Error summarizing text: {e}"

def highlight_risks(text):
    risk_keywords = [
        "liability", "terminate", "binding", "waive", "disclaimer", "warranty",
        "limitation", "arbitration", "indemnify", "legal"
    ]
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    risks = []
    for sentence in sentences:
        keywords_found = [keyword for keyword in risk_keywords if keyword in sentence.lower()]
        if keywords_found:
            level = "🔵 Minimal" if len(keywords_found) <= 2 else ("🟡 Caution" if len(keywords_found) <= 5 else "🔴 High Risk")
            risks.append({"sentence": sentence, "threat_level": level})
    return risks

if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    app.run(debug=True)
