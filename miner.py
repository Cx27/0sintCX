import json, time, random, os, re, csv
import logging
import psutil
from duckduckgo_search import DDGS

logging.basicConfig(
    level=logging.INFO, 
    format='[%(asctime)s] %(message)s', 
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler("miner.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)

FILE_CSV = 'Sample_data-alumni.csv'
FILE_JSON = 'data_alumni.json'

def load_db():
    if os.path.exists(FILE_JSON):
        try:
            with open(FILE_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def save_db(data_list):
    with open(FILE_JSON, 'w', encoding='utf-8') as f:
        json.dump(data_list, f, indent=4, ensure_ascii=False)

def safe_ddg_search(query, log_context, retries=2):
    for attempt in range(retries):
        try:
            with DDGS(timeout=10) as ddgs:
                delay = random.uniform(3, 6)
                logging.info(f"[*] {log_context} | Delay {delay:.1f}s...")
                time.sleep(delay)
                results = list(ddgs.text(query, region='id-id', max_results=1, safesearch='off'))
                return results if results else []
        except Exception as e:
            if "429" in str(e) or "Ratelimit" in str(e):
                logging.warning("🚨 [RATE LIMIT] Cooldown 60s...")
                time.sleep(60)
            else:
                time.sleep(5)
    return []

def extract_company_name(text):
    match_standard = re.search(r'\b(?:at|di)\b\s+([A-Za-z0-9\s&.\-]+?)(?:[.,|·\-/]|$)', text, re.IGNORECASE)
    if match_standard:
        comp = match_standard.group(1).strip()
        if len(comp) > 2 and not any(x in comp.lower() for x in ['umm', 'malang', 'sekarang', 'present', 'saat ini']):
            return comp.title()

    pola_prefix = r'\b(PT\.?|CV\.?|Apotek|RSUD?|Rumah Sakit|Klinik|Bank|Dinas|Kementerian|Universitas|Institut|Politeknik)\s+([A-Za-z0-9\s]+?)(?:[.,|·\-/]|$)'
    match_prefix = re.search(pola_prefix, text, re.IGNORECASE)
    
    if match_prefix:
        comp = f"{match_prefix.group(1)} {match_prefix.group(2)}".strip()
        if len(comp) > 3 and not any(x in comp.lower() for x in ['umm', 'malang', 'sekarang', 'present', 'saat ini']):
            return comp.title()

    return ""

def extract_contact_info(text):
    email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    phone = re.search(r'(\+62|08)[0-9]{8,11}', text)
    return {
        "email": email.group(0) if email else "-",
        "no_hp": phone.group(0) if phone else "-"
    }

def extract_data(target):
    nama, nim, prodi = target['nama'], target['nim'], target['prodi']
    nama_pendek = " ".join(nama.split()[:2]).lower()
    
    hasil = {
        "nama": nama, "nim": nim, "prodi": prodi, 
        "kategori": "Swasta", 
        "posisi": "Tidak ada rekam jejak digital.", 
        "tempat_bekerja": "-", 
        "alamat_bekerja": "-", 
        "email": "-", 
        "no_hp": "-", 
        "linkedin": "#", "instagram": "#", "facebook": "#", "tiktok": "#", 
        "company_ig": "#", 
        "last_updated": time.strftime("%Y-%m-%d %H:%M")
    }

    perusahaan_ditemukan = ""

    q_orang = f'site:linkedin.com/in/ "{nama_pendek}" ("UMM" OR "Malang")'
    res_orang = safe_ddg_search(q_orang, f"PROFILER -> {nama_pendek[:15].upper()}")
    
    for res in res_orang:
        url, snippet = res.get('href', '').lower(), res.get('body', '').lower()
        if ("umm" in snippet or "malang" in snippet) and "linkedin.com/in/" in url:
            hasil['linkedin'] = res.get('href')
            clean_body = re.sub(r'[^\x00-\x7F]+', '', res.get('body', ''))
            hasil['posisi'] = clean_body[:100] + "..."
            
            if any(x in snippet for x in ["pns", "dinas", "asn"]): hasil['kategori'] = "PNS"
            elif any(x in snippet for x in ["owner", "founder", "ceo"]): hasil['kategori'] = "Wirausaha"
            
            kontak = extract_contact_info(clean_body)
            if kontak['email'] != "-": hasil['email'] = kontak['email']
            if kontak['no_hp'] != "-": hasil['no_hp'] = kontak['no_hp']

            perusahaan_ditemukan = extract_company_name(clean_body)
            if perusahaan_ditemukan: hasil['tempat_bekerja'] = perusahaan_ditemukan
            break

    if perusahaan_ditemukan and len(perusahaan_ditemukan) > 3:
        res_alamat = safe_ddg_search(f'"{perusahaan_ditemukan}" alamat lokasi kantor', f"ALAMAT -> {perusahaan_ditemukan[:15]}")
        if res_alamat:
            hasil['alamat_bekerja'] = re.sub(r'[^\x00-\x7F]+', '', res_alamat[0].get('body', ''))[:100] + "..."
        
        res_comp_ig = safe_ddg_search(f'site:instagram.com "{perusahaan_ditemukan}"', f"CORP IG -> {perusahaan_ditemukan[:15]}")
        for res in res_comp_ig:
            url_ig = res.get('href', '')
            if url_ig.startswith('http') and "/p/" not in url_ig and "/explore/" not in url_ig:
                hasil['company_ig'] = url_ig
                break

    return hasil

def run_miner():
    logging.info("=== ⛏️ INTEL 8-POINT PIPELINE STARTED ===")
    existing_data = {item['nim']: item for item in load_db()}
    all_targets = []
    
    with open(FILE_CSV, mode='r', encoding='utf-8') as file:
        reader = list(csv.DictReader(file))
        reader.reverse() 
        for row in reader:
            if "Guru" not in row.get('Program Studi', ''):
                all_targets.append({
                    "nama": row.get('Nama Lulusan', '').strip(), 
                    "nim": row.get('NIM', '').strip(), 
                    "prodi": row.get('Program Studi', '').strip()
                })

    targets_to_scan = [t for t in all_targets if t['nim'] not in existing_data]
    logging.info(f"Target: {len(targets_to_scan)} alumni.\n")

    try:
        count = 0
        for target in targets_to_scan:
            count += 1
            result = extract_data(target)
            existing_data[target['nim']] = result
            save_db(list(existing_data.values()))
            
            cpu_usage = psutil.cpu_percent(interval=0.1)
            logging.info(f"✅ [CPU: {cpu_usage}%] Data {target['nama']} tersimpan! ({count}/{len(targets_to_scan)})\n")
                
    except KeyboardInterrupt:
        logging.info("\n🛑 Dihentikan paksa.")
    finally:
        save_db(list(existing_data.values()))

if __name__ == '__main__':
    run_miner()
