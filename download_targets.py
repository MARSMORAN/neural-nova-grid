import requests
import os

def download_pdb(pdb_id, output_path):
    print(f"[*] Downloading {pdb_id} from Protein Data Bank...")
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    r = requests.get(url)
    if r.status_code == 200:
        with open(output_path, "w") as f:
            f.write(r.text)
        print(f"[+] Saved {pdb_id} to {output_path}")
    else:
        print(f"[!] Failed to download {pdb_id}")

def main():
    target_dir = "./targets"
    os.makedirs(target_dir, exist_ok=True)
    
    targets = {
        "EGFR": "1M17",
        "PI3K": "1E7V",
        "mTOR": "4JSV",
        "PDGFR": "5GRN"
    }
    
    for name, pdb_id in targets.items():
        download_pdb(pdb_id, os.path.join(target_dir, f"{name.lower()}.pdb"))

if __name__ == "__main__":
    main()
