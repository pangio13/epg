import requests
import json
import time
import os
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Sorgente stabile 2026: SuperGuidaTV
API_URL = "https://api.superguidatv.it/v1/epg/channel/{id}/schedule?date={date}&device=web"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

def get_offset():
    # Aprile 2026: Ora legale italiana (+0200)
    return "+0200"

def clean_time(time_str):
    """Converte '2026-04-02 20:30:00' in '20260402203000'"""
    return time_str.replace("-", "").replace(":", "").replace(" ", "")

def fetch_epg():
    if not os.path.exists('src/channels.json'):
        print("Errore: src/channels.json non trovato")
        return

    with open('src/channels.json', 'r') as f:
        mapping = json.load(f)

    root = ET.Element("tv", {"generator-info-name": "SuperGuidaTV-XMLTV-Scraper"})
    
    # Header Canali
    for tvg_id in mapping.keys():
        ch = ET.SubElement(root, "channel", id=tvg_id)
        ET.SubElement(ch, "display-name").text = tvg_id

    # Scarichiamo oggi e domani
    dates = [datetime.now(), datetime.now() + timedelta(days=1)]
    
    for date in dates:
        d_str = date.strftime("%Y-%m-%d")
        print(f"\n--- Elaborazione data: {d_str} ---")
        
        for tvg_id, sg_id in mapping.items():
            try:
                url = API_URL.format(id=sg_id, date=d_str)
                r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
                
                if r.status_code == 200:
                    data = r.json()
                    programs = data.get("data", [])
                    
                    if not programs:
                        print(f"[-] {tvg_id}: Nessun dato")
                        continue
                        
                    count = 0
                    for p in programs:
                        # Parsing orari e creazione nodi
                        start = clean_time(p["startTime"])
                        end = clean_time(p["endTime"])
                        
                        p_node = ET.SubElement(root, "programme", 
                                              start=f"{start} {get_offset()}",
                                              stop=f"{end} {get_offset()}",
                                              channel=tvg_id)
                        
                        ET.SubElement(p_node, "title", lang="it").text = p.get("title", "N/A")
                        
                        if p.get("description"):
                            ET.SubElement(p_node, "desc", lang="it").text = p["description"]
                        
                        # Aggiunta opzionale: Categoria/Genere
                        if p.get("genre"):
                            ET.SubElement(p_node, "category", lang="it").text = p["genre"]
                            
                        count += 1
                    print(f"[OK] {tvg_id}: {count} programmi")
                else:
                    print(f"[!] {tvg_id}: Errore HTTP {r.status_code}")
                
                # Delay per rispettare i server (evita ban IP)
                time.sleep(0.3)
            except Exception as e:
                print(f"[Err] {tvg_id}: {e}")

    # Salvataggio finale
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
    print("\nOperazione completata con successo.")

if __name__ == "__main__":
    fetch_epg()
