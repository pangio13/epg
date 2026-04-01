import requests
import json
import time
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Configurazione
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
API_URL = "https://services.tivulaguida.it/api/epg/getProgramsByChannel"

def format_date(dt):
    return dt.strftime("%Y%m%d%H%M%S +0100")

def fetch_epg():
    with open('src/channels.json', 'r') as f:
        mapping = json.load(f)

    root = ET.Element("tv")
    
    # Genera tag <channel>
    for tvg_id in mapping.keys():
        channel_node = ET.SubElement(root, "channel", id=tvg_id)
        ET.SubElement(channel_node, "display-name").text = tvg_id

    # Recupera programmi per oggi e domani
    dates = [datetime.now(), datetime.now() + timedelta(days=1)]
    
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        print(f"Fetching data for {date_str}...")
        
        for tvg_id, tivu_id in mapping.items():
            try:
                params = {"id": tivu_id, "date": date_str}
                headers = {"User-Agent": USER_AGENT}
                response = requests.get(API_URL, params=params, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    for prog in data.get("programs", []):
                        # Crea nodo <programme>
                        start = datetime.fromtimestamp(prog["start_time"])
                        end = datetime.fromtimestamp(prog["end_time"])
                        
                        p_node = ET.SubElement(root, "programme", 
                                              start=format_date(start), 
                                              stop=format_date(end), 
                                              channel=tvg_id)
                        ET.SubElement(p_node, "title", lang="it").text = prog["title"]
                        if prog.get("description"):
                            ET.SubElement(p_node, "desc", lang="it").text = prog["description"]
                
                time.sleep(0.5) # Avoid rate limiting
            except Exception as e:
                print(f"Error fetching {tvg_id}: {e}")

    # Salva il file
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    fetch_epg()
