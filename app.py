from flask import Flask, jsonify, request
from flask_cors import CORS
from functools import wraps
import json
import os
import psutil

app = Flask(__name__)
CORS(app, supports_credentials=True, allow_headers="*", methods=["GET", "POST", "OPTIONS"])

if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

ADMIN_USER = os.environ.get("ADMIN_USER", "").strip()
ADMIN_PASS = os.environ.get("ADMIN_PASS", "").strip()
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "").strip()

FILE_JSON = 'data_alumni.json'
FILE_LOG = 'miner.log'

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return jsonify({}), 200
            
        token = request.headers.get('X-OSINT-Token')
        
        if not token:
            print("❌ TOKEN DITOLAK: Header kosong")
            return jsonify({'message': 'Akses Ditolak! Tiket Hilang.'}), 401
            
        if token.strip() != SECRET_TOKEN:
            print(f"❌ TOKEN MISMATCH: Datang '{token}', Diminta '{SECRET_TOKEN}'")
            return jsonify({'message': 'Akses Ditolak! Tiket Palsu.'}), 401
            
        return f(*args, **kwargs)
    return decorated

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    auth = request.json
    if not auth:
        return jsonify({'message': 'Data kosong'}), 400
        
    username = auth.get('username', '').strip()
    password = auth.get('password', '').strip()
    
    if username == ADMIN_USER and password == ADMIN_PASS:
        return jsonify({'token': SECRET_TOKEN})
        
    return jsonify({'message': 'Username atau Password salah!'}), 401

@app.route('/api/alumni', methods=['GET', 'OPTIONS'])
@token_required
def get_alumni():
    if os.path.exists(FILE_JSON):
        try:
            with open(FILE_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.sort(key=lambda x: x.get('last_updated', ''), reverse=True)
                return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify([])

@app.route('/api/telemetry', methods=['GET', 'OPTIONS'])
@token_required
def get_telemetry():
    cpu_usage = psutil.cpu_percent(interval=0.1)
    ram_usage = psutil.virtual_memory().percent
    
    logs = []
    if os.path.exists(FILE_LOG):
        try:
            with open(FILE_LOG, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                logs = [line.strip() for line in lines[-7:]]
        except:
            logs = ["Gagal membaca log file..."]
    else:
        logs = ["Menunggu miner.py dijalankan..."]

    return jsonify({
        "cpu": cpu_usage,
        "ram": ram_usage,
        "logs": logs
    })

if __name__ == '__main__':
    print("=== 🛡️ SECURE DASHBOARD API ONLINE [PORT 5000] ===")
    app.run(host='0.0.0.0', port=5000, debug=False)
