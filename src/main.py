import requests
import json
import time
import os
import urllib3
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Silenzia i warning SSL per compatibilità con i runner GitHub
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# NUOVO ENDPOINT 2026
API_URL = "https://www.tivu.tv/api/epg/getProgramsByChannel.aspx"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
REFERER = "https://www.tivu.tv/guida-programmi.html"

def get_offset():
    # Aprile 2026: Ora legale attiva (+0200)
    return "+0200"

def fetch_epg():
    if not os.path.exists('src/channels.json'):
        print("Errore: src/channels.json mancante")
        return

    with open('src/channels.json', 'r') as f:
        mapping = json.load(f)

    root = ET.Element("tv", {"generator-info-name": "GitHub-EPG-Generator"})
    
    # Header canali
    for tvg_id in mapping.keys():
        channel_node = ET.SubElement(root, "channel", id=tvg_id)
        ET.SubElement(channel_node, "display-name").text = tvg_id

    dates = [datetime.now(), datetime.now() + timedelta(days=1)]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": REFERER})

    for date in dates:
        d_str = date.strftime("%Y-%m-%d")
        print(f"\n--- Fetching {d_str} ---")
        
        for tvg_id, tivu_id in mapping.items():
            try:
                # Parametri aggiornati per la nuova API
                params = {"id": tivu_id, "d": d_str} 
                response = session.get(API_URL, params=params, timeout=10, verify=False)
                
                if response.status_code == 200:
                    data = response.json()
                    # L'API 2026 restituisce i programmi nella chiave "data" o direttamente
                    programs = data.get("data", []) if isinstance(data, dict) else data
                    
                    if not programs:
                        print(f"[-] {tvg_id}: Nessun dato")
                        continue

                    count = 0
                    for p in programs:
                        start_dt = datetime.fromtimestamp(p["start_time"])
                        stop_dt = datetime.fromtimestamp(p["end_time"])
                        
                        prog_node = ET.SubElement(root, "programme", 
                                                start=start_dt.strftime(f"%Y%m%d%H%M%S {get_offset()}"),
                                                stop=stop_dt.strftime(f"%Y%m%d%H%M%S {get_offset()}"),
                                                channel=tvg_id)
                        ET.SubElement(prog_node, "title", lang="it").text = p.get("title", "N/A")
                        if p.get("desc"):
                            ET.SubElement(prog_node, "desc", lang="it").text = p["desc"]
                        count += 1
                    print(f"[OK] {tvg_id}: {count} programmi")
                else:
                    print(f"[!] {tvg_id}: Errore {response.status_code}")
                
                time.sleep(0.2)
            except Exception as e:
                print(f"[Err] {tvg_id}: {e}")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
    print("\nFile epg.xml generato.")

if __name__ == "__main__":
    fetch_epg()
