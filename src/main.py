import requests
import json
import time
import os
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Configurazione - URL aggiornato alla versione Web più stabile
API_URL = "https://www.tivulaguida.it/api/epg/getProgramsByChannel"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
REFERER = "https://www.tivulaguida.it/"

def get_timezone_offset():
    # Dal 29 Marzo 2026 l'Italia è in ora legale (CEST, +0200)
    return "+0200"

def format_date(dt):
    offset = get_timezone_offset()
    return dt.strftime(f"%Y%m%d%H%M%S {offset}")

def fetch_epg():
    if not os.path.exists('src/channels.json'):
        print("Errore: src/channels.json non trovato!")
        return

    with open('src/channels.json', 'r') as f:
        mapping = json.load(f)

    root = ET.Element("tv", {
        "generator-info-name": "Tivusat-EPG-Generator",
        "source-info-name": "TivuLaGuida"
    })
    
    # 1. Crea i canali
    for tvg_id in mapping.keys():
        channel_node = ET.SubElement(root, "channel", id=tvg_id)
        ET.SubElement(channel_node, "display-name").text = tvg_id

    # 2. Recupera programmi (Oggi e Domani)
    dates = [datetime.now(), datetime.now() + timedelta(days=1)]
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Referer": REFERER,
        "Accept": "application/json"
    })

    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        print(f"--- Fetching: {date_str} ---")
        
        for tvg_id, tivu_id in mapping.items():
            try:
                params = {"id": tivu_id, "date": date_str}
                response = session.get(API_URL, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    # Verifichiamo se la chiave è 'programs' o se la lista è direttamente nel root
                    programs = data.get("programs", []) if isinstance(data, dict) else []
                    
                    if not programs:
                        print(f"DEBUG: Nessun programma per {tvg_id} (ID: {tivu_id})")
                        continue

                    for prog in programs:
                        start = datetime.fromtimestamp(prog["start_time"])
                        end = datetime.fromtimestamp(prog["end_time"])
                        
                        p_node = ET.SubElement(root, "programme", 
                                              start=format_date(start), 
                                              stop=format_date(end), 
                                              channel=tvg_id)
                        ET.SubElement(p_node, "title", lang="it").text = prog.get("title", "Nessun titolo")
                        if prog.get("description"):
                            ET.SubElement(p_node, "desc", lang="it").text = prog["description"]
                    
                    print(f"OK: {tvg_id} ({len(programs)} programmi)")
                else:
                    print(f"ERRORE: {tvg_id} risponde con status {response.status_code}")
                
                time.sleep(0.3) # Delay minimo per non essere bannati
            except Exception as e:
                print(f"ECCEZIONE per {tvg_id}: {e}")

    # 3. Scrittura file
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
    print("--- Generazione completata: epg.xml aggiornato ---")

if __name__ == "__main__":
    fetch_epg()
