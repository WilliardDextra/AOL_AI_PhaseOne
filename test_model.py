import os
from huggingface_hub import snapshot_download

# === 1. Set lokasi baru untuk cache ===
new_cache_dir = r"E:\huggingface_cache"
os.environ["HF_HOME"] = new_cache_dir
print(f"✅ HF_HOME diset ke: {os.environ['HF_HOME']}")

# === 2. Tes apakah direktori tersedia ===
if not os.path.exists(new_cache_dir):
    os.makedirs(new_cache_dir)
    print("📁 Folder cache baru dibuat.")

# === 3. Tes download model kecil (aman & cepat) ===
try:
    print("⬇️ Menguji download model kecil...")
    snapshot_download(repo_id="hf-internal-testing/tiny-random-clip")
    print("✅ Download berhasil! Cache kini disimpan di lokasi baru.")
except Exception as e:
    print("⚠️ Terjadi kesalahan:", e)
