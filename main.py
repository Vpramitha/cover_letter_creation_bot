from flask import Flask, render_template, request, send_file
import os
import json
from PyPDF2 import PdfReader
import requests
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

# Initialize Flask app
app = Flask(__name__)

# Paths for saving files
UPLOAD_FOLDER = './uploads'
OUTPUT_FOLDER = './output'
LLAMA_API_URL = "http://localhost:11434/api/generate"  # Update to your local Ollama API endpoint
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def extract_text_from_pdf(file_path):
    """Extract text from a PDF file."""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

def send_to_llama_streaming(prompt):
    """Send text to Llama2 and process streaming responses."""
    try:
        payload = {"model": "llama2", "prompt": prompt}
        headers = {"Content-Type": "application/json"}
        with requests.post(LLAMA_API_URL, json=payload, headers=headers, stream=True) as response:
            if response.status_code == 200:
                complete_response = ""
                for line in response.iter_lines():
                    if line:
                        chunk = line.decode('utf-8')
                        try:
                            chunk_data = json.loads(chunk)
                            complete_response += chunk_data.get("response", "")
                        except json.JSONDecodeError:
                            print(f"Invalid JSON chunk: {chunk}")
                return complete_response
            else:
                print(f"Error from Llama API: {response.status_code} - {response.text}")
                return "Error generating text."
    except Exception as e:
        print(f"Error contacting Llama API: {e}")
        return "Error generating text."

def create_pdf(content, output_path):
    """Generate a PDF with the provided content, ensuring text fits within page boundaries."""
    try:
        c = canvas.Canvas(output_path, pagesize=letter)
        c.setFont("Helvetica", 12)
        width, height = letter
        margin = 40
        line_height = 14
        max_width = width - 2 * margin
        y_position = height - margin

        for paragraph in content.split("\n"):
            lines = simpleSplit(paragraph, "Helvetica", 12, max_width)
            for line in lines:
                if y_position < margin + line_height:
                    c.showPage()
                    y_position = height - margin
                    c.setFont("Helvetica", 12)
                c.drawString(margin, y_position, line)
                y_position -= line_height

        c.save()
    except Exception as e:
        print(f"Error creating PDF: {e}")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Handle file uploads
        cv_file = request.files.get("cv")
        jd_file = request.files.get("job_description")
        
        if not cv_file or not jd_file:
            return "Both CV and Job Description files are required!", 400
        
        # Save uploaded files
        cv_path = os.path.join(UPLOAD_FOLDER, cv_file.filename)
        jd_path = os.path.join(UPLOAD_FOLDER, jd_file.filename)
        cv_file.save(cv_path)
        jd_file.save(jd_path)
        
        # Extract text from uploaded files
        cv_text = extract_text_from_pdf(cv_path) if cv_file.filename.endswith(".pdf") else cv_file.read().decode("utf-8")
        jd_text = extract_text_from_pdf(jd_path) if jd_file.filename.endswith(".pdf") else jd_file.read().decode("utf-8")
        
        # Generate prompt and send to Llama2
        prompt = f"Based on the CV:\n\n{cv_text}\n\nand the job description:\n\n{jd_text}\n\nCreate a professional cover letter.use the personal data from the given cv.don't use any other experience or project out side from the cv and write the letter according to the common cover letter structure and use the given names and addresses on the cv.the letter should be fit to the job description and the cv.use today as the date of the writing this letter."
        cover_letter = send_to_llama_streaming(prompt)

        # Save cover letter to PDF
        output_pdf = os.path.join(OUTPUT_FOLDER, "cover_letter.pdf")
        create_pdf(cover_letter, output_pdf)

        return render_template("result.html", cover_letter=cover_letter, download_link=output_pdf)

    return render_template("index.html")

@app.route("/download")
def download():
    """Download the generated PDF."""
    file_path = os.path.join(OUTPUT_FOLDER, "cover_letter.pdf")
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
