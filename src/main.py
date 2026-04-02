import requests
import gzip
import json
import os
import xml.etree.ElementTree as ET
from io import BytesIO

# Elenco fonti in ordine di priorità (Fallback)
SOURCES = [
    {
        "url": "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz",
        "is_gz": True,
        "name": "EPGShare01"
    },
    {
        "url": "http://epg-guide.com/dtt.xml",
        "is_gz": False,
        "name": "EPG-Guide"
    },
    {
        "url": "https://iptv-org.github.io/epg/guides/it/superguidatv.it.epg.xml",
        "is_gz": False,
        "name": "IPTV-Org (SuperGuidaTV)"
    }
]

def load_mapping():
    """Carica la mappatura dei canali da file locale."""
    if not os.path.exists('src/channels.json'):
        print("[!] Errore: src/channels.json mancante.")
        return {}
    with open('src/channels.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_and_parse(source):
    """Scarica e converte in albero XML la sorgente specificata."""
    print(f"\nScaricamento sorgente [{source['name']}]: {source['url']}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EPG-Aggregator/1.0"}
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

    # Inversione mappa per ricerca O(1): { "Nome_Sorgente": "Mio_ID_Target" }
    reverse_map = {}
    for target_id, source_ids in mapping.items():
        for s_id in source_ids:
            reverse_map[s_id] = target_id

    new_root = ET.Element("tv", {
        "generator-info-name": "GitHub-Multi-Source-EPG",
        "source-info-name": "EPGShare+EPGGuide+IPTVOrg"
    })

    # Inizializzazione tracciamento canali
    added_channels = list(mapping.keys())
    program_count = {ch: 0 for ch in added_channels}
    
    # Inserimento tag base <channel>
    for target_id in added_channels:
        ch_node = ET.SubElement(new_root, "channel", id=target_id)
        ET.SubElement(ch_node, "display-name").text = target_id

    # Iterazione sulle fonti a cascata
    for source in SOURCES:
        if all(count > 0 for count in program_count.values()):
            print("\n[INFO] Tutti i canali sono stati popolati. Stop aggregazione.")
            break

        source_root = fetch_and_parse(source)
        if source_root is None:
            continue

        print(f"Filtro e associazione programmi da {source['name']}...")
        added_from_this_source = 0
        
        for prog in source_root.findall('programme'):
            source_ch_id = prog.get('channel')
            
            if source_ch_id in reverse_map:
                target_ch_id = reverse_map[source_ch_id]
                
                # Evita duplicati: aggiunge solo se il canale è ancora a 0 programmi
                if program_count[target_ch_id] == 0 or getattr(prog, 'override_flag', False):
                    new_prog = ET.Element("programme", prog.attrib)
                    new_prog.set('channel', target_ch_id)
                    
                    for child in prog:
                        new_prog.append(child)
                    
                    new_root.append(new_prog)
                    # Flag temporaneo per conteggio
                    prog.set('added_to', target_ch_id) 

        # Aggiorna i contatori per la sorgente corrente
        for prog in source_root.findall('programme'):
            target = prog.get('added_to')
            if target:
                program_count[target] += 1
                added_from_this_source += 1

        print(f"[+] {added_from_this_source} programmi estratti da {source['name']}.")

    # --- DETTAGLIO CANALI E STATISTICHE FINALI ---
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
            print(f"[VUOTO] {ch}: Nessun dato in nessuna sorgente")

    # Scrittura su disco
    try:
        tree = ET.ElementTree(new_root)
        ET.indent(tree, space="  ")
        tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
    except Exception as e:
        print(f"\n[ERR] Errore critico durante la scrittura del file epg.xml: {e}")
        return
    
    # OUTPUT DI CONFERMA FINALE
    coverage_percentage = (success_count / total_channels) * 100 if total_channels > 0 else 0
    
    print("\n==================================================")
    if success_count == total_channels:
        print(f"✅ SUCCESSO TOTALE: Guida generata per {success_count}/{total_channels} canali ({coverage_percentage:.1f}%).")
    else:
        print(f"⚠️ SUCCESSO PARZIALE: Guida generata per {success_count}/{total_channels} canali ({coverage_percentage:.1f}%).")
        print(f"Canali mancanti ({len(mancanti)}): {', '.join(mancanti)}")
        print("-> Azione: Verifica i nomi in src/channels.json per i canali mancanti.")
    print("==================================================\n")

if __name__ == "__main__":
    build_epg()
