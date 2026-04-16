import requests
import gzip
import json
import os
import xml.etree.ElementTree as ET
from io import BytesIO

SOURCES = [
    {"url": "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz", "is_gz": True, "name": "EPGShare"},
    {"url": "http://epg-guide.com/dtt.xml", "is_gz": False, "name": "EPG-Guide"},
    {"url": "https://www.open-epg.com/files/italy1.xml", "is_gz": False, "name": "OpenEPG"},
    {"url": "https://iptv-epg.org/files/epg-it.xml.gz", "is_gz": True, "name": "IPTV-EPG"}
]

# Soglia minima: >30 programmi per validare il canale come definitivo
MIN_PROGRAMS = 31 

def load_mapping():
    if not os.path.exists('src/channels.json'):
        print("[!] Errore: src/channels.json mancante.")
        return {}
    with open('src/channels.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_and_parse(source):
    print(f"\nScaricamento sorgente [{source['name']}]: {source['url']}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(source['url'], headers=headers, timeout=30)
        response.raise_for_status()
        
        if source['is_gz']:
            with gzip.GzipFile(fileobj=BytesIO(response.content)) as gz:
                tree = ET.parse(gz)
        else:
            tree = ET.parse(BytesIO(response.content))
            
        print(f"[OK] {source['name']} parsato con successo.")
        return tree.getroot()
    except Exception as e:
        print(f"[ERR] Fallimento per {source['name']}: {e}")
        return None

def build_epg():
    mapping = load_mapping()
    if not mapping:
        return

    reverse_map = {}
    for target_id, source_ids in mapping.items():
        for s_id in source_ids:
            reverse_map[s_id.lower().strip()] = target_id

    new_root = ET.Element("tv", {
        "generator-info-name": "GitHub-Multi-Source-EPG",
        "source-info-name": "EPGShare+EPGGuide+OpenEPG+IPTVEPG"
    })

    added_channels = list(mapping.keys())
    epg_buffer = {ch: [] for ch in added_channels}
    
    for target_id in added_channels:
        ch_node = ET.SubElement(new_root, "channel", id=target_id)
        ET.SubElement(ch_node, "display-name").text = target_id

    for source in SOURCES:
        if all(len(epg_buffer[ch]) >= MIN_PROGRAMS for ch in added_channels):
            print(f"\n[INFO] Tutti i canali hanno superato la soglia ({MIN_PROGRAMS}+). Stop aggregazione.")
            break

        source_root = fetch_and_parse(source)
        if source_root is None:
            continue

        print(f"Valutazione palinsesti per {source['name']}...")
        
        local_channel_map = {}
        for ch in source_root.findall('channel'):
            c_id = ch.get('id', '')
            c_id_lower = c_id.lower().strip()
            disp_elem = ch.find('display-name')
            c_name = disp_elem.text.lower().strip() if disp_elem is not None and disp_elem.text else ""

            if c_id_lower in reverse_map:
                local_channel_map[c_id] = reverse_map[c_id_lower]
            elif c_name in reverse_map:
                local_channel_map[c_id] = reverse_map[c_name]

        temp_buffer = {ch: [] for ch in added_channels}
        
        for prog in source_root.findall('programme'):
            source_ch_id = prog.get('channel')
            if source_ch_id in local_channel_map:
                target_ch_id = local_channel_map[source_ch_id]
                temp_buffer[target_ch_id].append(prog)

        for ch in added_channels:
            current_len = len(epg_buffer[ch])
            new_len = len(temp_buffer[ch])
            
            # Sovrascrittura: fallita la soglia E nuovo palinsesto quantitativamente maggiore
            if current_len < MIN_PROGRAMS and new_len > current_len:
                epg_buffer[ch] = temp_buffer[ch]
                for prog in epg_buffer[ch]:
                    prog.set('channel', ch)

    print("\n[INFO] Scrittura dei palinsesti ottimali nel file XML...")
    for ch, progs in epg_buffer.items():
        for p in progs:
            new_root.append(p)

    print("\n--- DETTAGLIO CANALI ---")
    mancanti = []
    success_count = 0
    total_channels = len(added_channels)

    for ch, progs in epg_buffer.items():
        count = len(progs)
        if count >= MIN_PROGRAMS:
            success_count += 1
            print(f"[OK] {ch}: {count} programmi")
        elif count > 0:
            mancanti.append(ch)
            print(f"[INCOMPLETO/MASSIMO TROVATO] {ch}: Conservati {count} programmi")
        else:
            mancanti.append(ch)
            print(f"[VUOTO] {ch}: Nessun dato in tutte le fonti")

    try:
        tree = ET.ElementTree(new_root)
        ET.indent(tree, space="  ")
        tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
    except Exception as e:
        print(f"\n[ERR] Errore critico salvataggio: {e}")
        return
    
    coverage = (success_count / total_channels) * 100 if total_channels > 0 else 0
    
    print("\n==================================================")
    if success_count == total_channels:
        print(f"✅ SUCCESSO TOTALE: {success_count}/{total_channels} canali ottimali ({coverage:.1f}%).")
    else:
        print(f"⚠️ SUCCESSO PARZIALE: {success_count}/{total_channels} canali ottimali ({coverage:.1f}%).")
        print(f"Sotto soglia ({len(mancanti)}): {', '.join(mancanti)}")
    print("==================================================\n")

if __name__ == "__main__":
    build_epg()
