import requests
import json
import time
import os
import urllib3
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# --- CONFIGURAZIONE ---
# Disabilita i warning SSL per le connessioni non verificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# URL senza 'www' per evitare errori di mismatch nel certificato SSL
API_URL = "https://tivulaguida.it/api/epg/getProgramsByChannel"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
REFERER = "https://tivulaguida.it/"

def get_timezone_offset():
    """
    Ritorna l'offset orario per l'Italia.
    Aprile 2026 = Ora Legale (CEST) -> +0200
    """
    return "+0200"

def format_date(dt):
    """Formatta la data nel formato standard XMLTV: YYYYMMDDHHMMSS +offset"""
    offset = get_timezone_offset()
    return dt.strftime(f"%Y%m%d%H%M%S {offset}")

def fetch_epg():
    # Verifica esistenza del file di mappatura
    if not os.path.exists('src/channels.json'):
        print("ERRORE CRITICO: src/channels.json non trovato!")
        return

    with open('src/channels.json', 'r') as f:
        mapping = json.load(f)

    # Inizializzazione dell'albero XML
    root = ET.Element("tv", {
        "generator-info-name": "Tivusat-EPG-Generator-Personal",
        "source-info-name": "TivuLaGuida-Official"
    })
    
    # 1. Definizione dei canali (Header XMLTV)
    for tvg_id in mapping.keys():
        channel_node = ET.SubElement(root, "channel", id=tvg_id)
        ET.SubElement(channel_node, "display-name").text = tvg_id

    # 2. Recupero dati per Oggi e Domani
    dates = [datetime.now(), datetime.now() + timedelta(days=1)]
    
    # Configurazione sessione HTTP
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Referer": REFERER,
        "Accept": "application/json"
    })

    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        print(f"\n--- Elaborazione data: {date_str} ---")
        
        for tvg_id, tivu_id in mapping.items():
            try:
                params = {"id": tivu_id, "date": date_str}
                # verify=False risolve l'errore SSL riscontrato nel log
                response = session.get(API_URL, params=params, timeout=15, verify=False)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Gestione diverse strutture JSON possibili
                    programs = []
                    if isinstance(data, dict):
                        programs = data.get("programs", [])
                    elif isinstance(data, list):
                        programs = data

                    if not programs:
                        print(f"[-] {tvg_id}: Nessun dato disponibile")
                        continue

                    count = 0
                    for prog in programs:
                        # Parsing orari (Timestamp Unix)
                        start = datetime.fromtimestamp(prog["start_time"])
                        end = datetime.fromtimestamp(prog["end_time"])
                        
                        # Creazione nodo programma
                        p_node = ET.SubElement(root, "programme", 
                                              start=format_date(start), 
                                              stop=format_date(end), 
                                              channel=tvg_id)
                        
                        ET.SubElement(p_node, "title", lang="it").text = prog.get("title", "Senza Titolo")
                        
                        desc = prog.get("description")
                        if desc:
                            ET.SubElement(p_node, "desc", lang="it").text = desc
                        
                        count += 1
                    
                    print(f"[+] {tvg_id}: Scaricati {count} programmi")
                else:
                    print(f"[!] {tvg_id}: Errore HTTP {response.status_code}")
                
                # Piccola pausa per evitare il rate limiting (ban IP)
                time.sleep(0.4) 
                
            except Exception as e:
                print(f"[X] Errore per {tvg_id}: {str(e)}")

    # 3. Salvataggio finale
    try:
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0) # Rende l'XML leggibile (Python 3.9+)
        tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
        print("\n--- OPERAZIONE COMPLETATA: epg.xml generato con successo ---")
    except Exception as e:
        print(f"Errore durante il salvataggio del file: {e}")

if __name__ == "__main__":
    fetch_epg()
