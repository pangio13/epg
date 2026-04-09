import requests
import gzip
import json
import os
import xml.etree.ElementTree as ET
from io import BytesIO

SOURCES = [
    {"url": "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz", "is_gz": True, "name": "EPGShare"},
    {"url": "https://iptv-epg.org/files/epg-it.xml.gz", "is_gz": True, "name": "IPTV-EPG"},
    {"url": "https://www.open-epg.com/files/italy1.xml.gz", "is_gz": True, "name": "OpenEPG-1"},
    {"url": "https://epg-guide.com/it.gz", "is_gz": True, "name": "EPG-Guide"}
]

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

    # Inversione mappa case-insensitive e normalizzata
    reverse_map = {}
    for target_id, source_ids in mapping.items():
        for s_id in source_ids:
            reverse_map[s_id.lower().strip()] = target_id

    new_root = ET.Element("tv", {
        "generator-info-name": "GitHub-Multi-Source-EPG",
        "source-info-name": "EPGShare+IPTVEPG+Lululla+EPGGuide"
    })

    added_channels = list(mapping.keys())
    program_count = {ch: 0 for ch in added_channels}
    
    for target_id in added_channels:
        ch_node = ET.SubElement(new_root, "channel", id=target_id)
        ET.SubElement(ch_node, "display-name").text = target_id

    for source in SOURCES:
        if all(count > 0 for count in program_count.values()):
            print("\n[INFO] Tutti i canali sono popolati. Stop aggregazione.")
            break

        source_root = fetch_and_parse(source)
        if source_root is None:
            continue

        print(f"Mappatura dinamica dei canali per {source['name']}...")
        
        # MAPPATURA BIDIREZIONALE (Match su ID e su Nome Testuale)
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

        added_from_this_source = 0
        
        for prog in source_root.findall('programme'):
            source_ch_id = prog.get('channel')
            
            if source_ch_id in local_channel_map:
                target_ch_id = local_channel_map[source_ch_id]
                
                if program_count[target_ch_id] == 0:
                    new_prog = ET.Element("programme", prog.attrib)
                    new_prog.set('channel', target_ch_id)
                    
                    for child in prog:
                        new_prog.append(child)
                    
                    new_root.append(new_prog)
                    prog.set('added_to', target_ch_id) 

        for prog in source_root.findall('programme'):
            target = prog.get('added_to')
            if target:
                program_count[target] += 1
                added_from_this_source += 1

        print(f"[+] {added_from_this_source} programmi estratti da {source['name']}.")

    print("\n--- DETTAGLIO CANALI ---")
    mancanti = []
    success_count = 0
    total_channels = len(program_count)

    for ch, count in program_count.items():
        if count > 0:
            success_count += 1
            print(f"[OK] {ch}: {count} programmi")
        else:
            mancanti.append(ch)
            print(f"[VUOTO] {ch}: Nessun dato")

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
        print(f"✅ SUCCESSO TOTALE: {success_count}/{total_channels} canali ({coverage:.1f}%).")
    else:
        print(f"⚠️ SUCCESSO PARZIALE: {success_count}/{total_channels} canali ({coverage:.1f}%).")
        print(f"Mancanti ({len(mancanti)}): {', '.join(mancanti)}")
    print("==================================================\n")

if __name__ == "__main__":
    build_epg()
