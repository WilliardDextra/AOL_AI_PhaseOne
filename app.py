from flask import Flask, render_template, request, jsonify
import os
import requests
from dotenv import load_dotenv
import base64
import json
import mimetypes

# Memuat variabel lingkungan dari file .env
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# --- KONFIGURASI API GEMINI ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("FATAL ERROR: GEMINI_API_KEY not found in .env file. Analisis akan gagal.")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"

# --- FUNGSI UTAMA ---

@app.route('/')
def home():
    # Membuat folder uploads jika belum ada
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return render_template('index.html', has_api_key=bool(GEMINI_API_KEY))

def get_mime_type(filepath):
    """Menentukan MIME type gambar secara lebih andal."""
    mime, _ = mimetypes.guess_type(filepath)
    if mime and mime.startswith('image/'):
        return mime
    # Default ke JPEG jika tidak dapat ditebak (pilihan aman)
    return 'image/jpeg' 

def analyze_with_gemini(image_path, food_name, food_weight):
    """Mengirim data multimodal (gambar, nama, berat) ke Gemini API."""
    json_string = None 
    
    try:
        # 1. Baca dan encode gambar ke Base64
        image_mime_type = get_mime_type(image_path)
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

        # 2. Instruksi Sistem dan Skema JSON
        system_prompt = (
            "You are a professional Food Waste Reduction and Nutrition Analyst. "
            "Your task is to analyze the provided food image and text inputs to generate a structured analysis. "
            "You MUST estimate the shelf life, provide nutritional value, and list potential allergens. "
            "Base the analysis on the image, the user-provided name ('" + food_name + "'), and the estimated weight/amount ('" + food_weight + "')."
            "Provide the response ONLY as a JSON object that strictly adheres to the provided schema."
        )
        
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "foodNameIdentified": {"type": "STRING"},
                "servingDetails": {"type": "STRING"},
                "expirationAnalysis": {
                    "type": "OBJECT",
                    "properties": {
                        "estimatedShelfLife": {"type": "STRING"},
                        "storageRecommendation": {"type": "STRING"}
                    },
                    "required": ["estimatedShelfLife", "storageRecommendation"]
                },
                "nutritionFacts": {
                    "type": "OBJECT",
                    "properties": {
                        "Calories": {"type": "STRING"},
                        "Protein": {"type": "STRING"},
                        "Fat": {"type": "STRING"},
                        "Carbs": {"type": "STRING"}
                    },
                    "required": ["Calories", "Protein", "Fat", "Carbs"]
                },
                "potentialAllergens": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"}
                }
            },
            "required": ["foodNameIdentified", "expirationAnalysis", "nutritionFacts", "potentialAllergens"]
        }


        # 3. Payload API
        prompt = (
            f"Analyze the food: {food_name}. "
            f"Estimated amount/weight: {food_weight}. "
            "Provide the requested structured analysis."
        )

        payload = {
            # 🌟 PERBAIKAN KRITIS: System Instruction di tingkat teratas payload
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": image_mime_type, 
                                "data": encoded_image
                            }
                        }
                    ]
                }
            ],
            # generationConfig hanya menampung schema dan mime type respons
            "generationConfig": { 
                "responseMimeType": "application/json",
                "responseSchema": json_schema
            }
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", 
                                 headers=headers, 
                                 data=json.dumps(payload))
        
        response.raise_for_status() 

        # 4. Parsing Hasil
        result_json = response.json()
        
        # Ekstrak teks JSON dari respons Gemini
        json_string = result_json.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
        
        if not json_string:
             return {"error": "Gemini response was empty. The model might have been blocked or failed to generate JSON."}, "Unknown"
             
        # Parsing JSON yang dihasilkan
        parsed_data = json.loads(json_string)
        
        return parsed_data, parsed_data.get("foodNameIdentified", "Unknown")

    except requests.exceptions.RequestException as e:
        error_msg = f"API Request Failed: {e}"
        if e.response is not None and e.response.status_code == 400:
             error_msg += f" | Server Response: {e.response.text[:150]}"
        return {"error": error_msg}, "Unknown"
    except json.JSONDecodeError:
        return {"error": f"Failed to parse JSON response from Gemini. The AI might not have returned pure JSON. Raw: {json_string[:100] if json_string else 'No raw data'}..."}, "Unknown"
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}, "Unknown"


@app.route('/analyze', methods=['POST'])
def analyze():
    # Import mimetypes di sini agar tidak ada potensi error impor di luar fungsi
    import mimetypes 
    
    if not GEMINI_API_KEY:
        return render_template('index.html', result={"error": "Missing GEMINI_API_KEY in .env file."}, has_api_key=False)

    # 1. Validasi dan Ambil Data Form
    if 'file' not in request.files:
        return render_template('index.html', error="No file uploaded.")
    
    file = request.files['file']
    food_name = request.form.get('foodName', 'Nama Makanan Tidak Diketahui')
    food_weight = request.form.get('foodWeight', 'Berat Tidak Diketahui')
    
    if file.filename == '':
        return render_template('index.html', error="Please choose a file.")
    
    # 2. Simpan File Temporer
    upload_folder = app.config['UPLOAD_FOLDER']
    filename = file.filename
    # Membuat nama file unik untuk menghindari konflik 
    unique_filename = f"{os.path.splitext(filename)[0]}_{os.urandom(4).hex()}{os.path.splitext(filename)[1]}"
    filepath = os.path.join(upload_folder, unique_filename)
    
    try:
        file.save(filepath)
    except Exception as e:
        return render_template('index.html', result={"error": f"Failed to save file locally: {e}"})

    # 3. Analisis dengan Gemini
    gemini_result, detected_food = analyze_with_gemini(filepath, food_name, food_weight)

    # 4. Hapus File Temporer
    try:
        # File tidak dihapus agar dapat ditampilkan di frontend
        pass 
    except Exception as e:
        print(f"Error deleting file: {e}")
        
    # 5. Mengirimkan hasil ke template
    image_url_path = request.url_root + 'static/uploads/' + unique_filename

    if "error" in gemini_result:
        return render_template('index.html', result=gemini_result, image_url=image_url_path)
    else:
        gemini_result['filename'] = unique_filename
        return render_template('index.html', result=gemini_result, image_url=image_url_path)

if __name__ == '__main__':
    app.run(debug=True)
