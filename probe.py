import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    print("Fetching...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    domains = ["annas-archive.se", "annas-archive.pm", "annas-archive.li"]
    for d in domains:
        try:
            print(f"Trying {d}...")
            r = requests.get(f'https://{d}/search?q=harry+potter', verify=False, headers=headers)
            print(f"Status for {d}: {r.status_code}")
            if r.status_code == 200:
                with open('annas_sample.html', 'w', encoding='utf-8') as f:
                    f.write(r.text)
                print("Success!")
                break
        except Exception as e:
            print(f"Error with {d}: {e}")
except Exception as e:
    print(f"Error: {e}")
