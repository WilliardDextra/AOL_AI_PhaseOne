from flask import Flask, render_template, request, url_for
import os
import requests
from dotenv import load_dotenv
import base64
import json
import mimetypes
import os.path
import random

# Memuat variabel lingkungan dari file .env
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# --- KONFIGURASI API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("PERINGATAN: GEMINI_API_KEY tidak ditemukan di .env. Analisis akan gagal.")

# 🌟 PERBAIKAN: Beralih ke 'gemini-2.0-flash-lite-preview-02-05'
# Varian "Lite" ini ringan dan sering memiliki kuota terpisah dari model utama.
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite-preview-02-05:generateContent"

# --- URL ALTERNATIF GRATIS (OpenStreetMap) ---
NOMINATIM_API_URL = "https://nominatim.openstreetmap.org/search"
OSRM_API_URL = "https://router.project-osrm.org/route/v1/driving"

# --- FUNGSI PETA (OSM) ---

def geocode_address(address):
    """Mengubah alamat menjadi koordinat Lat/Long menggunakan Nominatim (OSM)."""
    try:
        headers = {'User-Agent': 'FoodLinkApp/1.0 (Student Project)'} 
        response = requests.get(NOMINATIM_API_URL, params={
            'q': address,
            'format': 'json',
            'limit': 1
        }, headers=headers, timeout=10)
        
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            location = data[0]
            return f"{location['lat']},{location['lon']}" 
        else:
            return None
    except Exception as e:
        print(f"Geocoding Error: {e}")
        return None

def get_shortest_route(origin_addr, dest_addr):
    """Mendapatkan rute terpendek menggunakan OSRM dengan Penyesuaian Traffic."""
    
    # 1. Geocoding
    origin_coords = geocode_address(origin_addr)
    dest_coords = geocode_address(dest_addr)
    
    if not origin_coords or not dest_coords:
        return {"error": "Alamat tidak ditemukan di peta. Coba nama kota/jalan yang lebih umum."}, None, None
        
    try:
        # 2. Request Rute ke OSRM
        origin_lon_lat = ",".join(origin_coords.split(',')[::-1]) 
        dest_lon_lat = ",".join(dest_coords.split(',')[::-1])
        
        # Request geometri penuh untuk digambar di peta
        route_url = f"{OSRM_API_URL}/{origin_lon_lat};{dest_lon_lat}?overview=full&geometries=geojson"
        
        response = requests.get(route_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['code'] == 'Ok':
            route = data['routes'][0]
            
            distance_meters = route['distance']
            raw_duration_seconds = route['duration']
            
            # 🌟 LOGIC UPDATE: Traffic Factor ditingkatkan ke 1.7
            # OSRM menghitung waktu berdasarkan jalan kosong.
            # Multiplier 1.7x mengasumsikan kondisi lalu lintas padat/realistis.
            TRAFFIC_MULTIPLIER = 1.7 
            adjusted_duration_seconds = raw_duration_seconds * TRAFFIC_MULTIPLIER
            
            distance_km = f"{distance_meters / 1000:.1f} km"
            duration_min = f"{int(adjusted_duration_seconds // 60)} menit"
            
            route_data = {
                "distance": distance_km,
                "duration": duration_min,
                "summary": route['legs'][0].get('summary', 'Rute Tercepat'),
                "geometry": route['geometry'],
                "start_coords": origin_coords.split(','),
                "end_coords": dest_coords.split(',')
            }
            return None, route_data, True
        else:
            return {"error": "Rute tidak ditemukan."}, None, None
            
    except Exception as e:
        return {"error": f"Gagal menghitung rute: {e}"}, None, None

# --- FUNGSI GEMINI (FOOD ANALYSIS) ---

def get_mime_type(filepath):
    mime, _ = mimetypes.guess_type(filepath)
    if mime and mime.startswith('image/'):
        return mime
    return 'image/jpeg' 

def analyze_with_gemini(image_path, food_name, food_weight):
    try:
        image_mime_type = get_mime_type(image_path)
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

        system_prompt = (
            "You are a Food Waste & Nutrition Analyst. Analyze the food image. "
            "Input: Name='" + food_name + "', Amount='" + food_weight + "'. "
            "Task: Estimate shelf life, nutritional facts, and allergens. "
            "Output JSON ONLY."
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

        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{
                "parts": [
                    {"text": f"Analyze this food: {food_name}, Weight: {food_weight}"},
                    {"inlineData": {"mimeType": image_mime_type, "data": encoded_image}}
                ]
            }],
            "generationConfig": { 
                "responseMimeType": "application/json",
                "responseSchema": json_schema
            }
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", 
                                 headers=headers, data=json.dumps(payload), timeout=30)
        
        if response.status_code != 200:
            return {"error": f"Gemini API Error ({response.status_code}): {response.text}"}, "Unknown"

        result_json = response.json()
        try:
            json_string = result_json['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError):
             return {"error": "AI response error."}, "Unknown"
             
        parsed_data = json.loads(json_string)
        return parsed_data, parsed_data.get("foodNameIdentified", "Unknown")

    except Exception as e:
        return {"error": f"System Error: {e}"}, "Unknown"

# --- ROUTES ---

@app.route('/')
def home():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    return render_template('index.html', has_api_key=bool(GEMINI_API_KEY))

@app.route('/analyze', methods=['POST'])
def analyze():
    has_key = bool(GEMINI_API_KEY)
    if not has_key:
        return render_template('index.html', result={"error": "API Key tidak ditemukan."}, has_api_key=False)

    if 'file' not in request.files:
        return render_template('index.html', error="File tidak ditemukan.", has_api_key=has_key)
    
    file = request.files['file']
    food_name = request.form.get('foodName', '-')
    food_weight = request.form.get('foodWeight', '-')
    origin_address = request.form.get('originAddress')
    dest_address = request.form.get('destAddress')
    
    if file.filename == '':
        return render_template('index.html', error="Pilih file gambar.", has_api_key=has_key)
    
    filename = file.filename
    unique_filename = f"{os.path.splitext(filename)[0]}_{os.urandom(4).hex()}{os.path.splitext(filename)[1]}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)

    gemini_result, detected_food = analyze_with_gemini(filepath, food_name, food_weight)
    route_error, route_data, route_success = get_shortest_route(origin_address, dest_address)
    
    final_result = {}
    if "error" in gemini_result:
        final_result.update(gemini_result)
    else:
        final_result.update(gemini_result)

    if route_success:
        final_result['route_data'] = route_data
    elif route_error:
        final_result['route_error'] = route_error['error']
        
    image_url_path = url_for('static', filename='uploads/' + unique_filename)

    return render_template('index.html', 
                           result=final_result, 
                           image_url=image_url_path,
                           has_api_key=has_key, 
                           food_name=food_name,
                           food_weight=food_weight,
                           origin_address=origin_address,
                           dest_address=dest_address)

if __name__ == '__main__':
    app.run(debug=True)