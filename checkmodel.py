import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("❌ API Key tidak ditemukan di .env")
else:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    response = requests.get(url)
    
    if response.status_code == 200:
        models = response.json().get('models', [])
        print("✅ Koneksi Berhasil! Berikut model yang tersedia untuk Anda:")
        for model in models:
            if 'generateContent' in model.get('supportedGenerationMethods', []):
                print(f" - {model['name']}")
    else:
        print(f"❌ Gagal mengambil daftar model: {response.text}")