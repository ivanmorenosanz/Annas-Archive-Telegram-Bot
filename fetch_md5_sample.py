import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

url = "https://annas-archive.pm/md5/8efbf8e9f8b4592c7b0dbedec9c0ec05"
print(f"Fetching {url}...")
try:
    r = requests.get(url, verify=False, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        with open('md5_sample.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        print("Saved to md5_sample.html")
    else:
        print("Failed to fetch.")
except Exception as e:
    print(f"Error: {e}")
