import requests
from bs4 import BeautifulSoup
import urllib3
import logging

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOMAINS = ["annas-archive.li", "annas-archive.se", "annas-archive.pm", "annas-archive.org"]
CURRENT_DOMAIN = None

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def find_working_domain():
    global CURRENT_DOMAIN
    if CURRENT_DOMAIN:
        return CURRENT_DOMAIN
    
    for domain in DOMAINS:
        try:
            url = f"https://{domain}/search?q=test"
            logger.info(f"Testing {domain}...")
            response = requests.get(url, headers=HEADERS, verify=False, timeout=5)
            if response.status_code == 200:
                CURRENT_DOMAIN = domain
                logger.info(f"Found working domain: {CURRENT_DOMAIN}")
                return CURRENT_DOMAIN
        except Exception as e:
            logger.warning(f"Failed to connect to {domain}: {e}")
            continue
    
    return None

def search_books(query):
    domain = find_working_domain()
    if not domain:
        logger.error("No working domain found.")
        return []

    url = f"https://{domain}/search"
    params = {'q': query}
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, verify=False)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Search request failed: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    results = []
    
    seen_md5s = set()
    
    # Iterate through potential result items. 
    # Based on the HTML structure in annas_sample.html:
    # <div class="flex pt-3 pb-3 border-b ...">
    #   ...
    #   <div class="max-w-full ...">
    #     <div>
    #       <a href="/md5/..." ...>Title</a>
    #       <a href="/search?q=..." ...>Author</a>
    #     </div>
    #     ...
    #     <div class="text-gray-800 ... leading-[1.2] mt-2">File Info (Format, Size, etc.)</div>
    #   </div>
    # </div>
    
    for row in soup.find_all('div', class_=lambda c: c and 'flex' in c and 'border-b' in c and 'border-gray-100' in c):
        try:
            # Find Title link with /md5/ href and text-lg class
            title_link = None
            for a in row.find_all('a', href=True):
                if '/md5/' in a['href'] and 'text-lg' in a.get('class', []):
                    title_link = a
                    break
            
            if not title_link:
                continue
                
            md5 = title_link['href'].split('/md5/')[1]
            if md5 in seen_md5s:
                continue
            
            # Get only direct text from title link (not nested elements)
            # Use .string or iterate only direct strings
            title_parts = []
            for child in title_link.children:
                if isinstance(child, str):
                    title_parts.append(child.strip())
            title = ' '.join(title_parts).strip()
            
            # Fallback if no direct text found
            if not title:
                title = title_link.get_text(strip=True)
                # Clean up: remove everything after common garbage patterns
                for pattern in ['Read more', 'nexusstc/', 'lgli/', 'lgrs/']:
                    if pattern in title:
                        title = title.split(pattern)[0].strip()
            
            # Find Author - first /search?q= link that looks like an author name
            author_str = "Unknown Author"
            for a in row.find_all('a', href=True):
                if '/search?q=' in a['href'] and a != title_link:
                    text = a.get_text(strip=True)
                    # Skip if it looks like a file path or garbage
                    if text and not any(x in text for x in ['/', '.pdf', '.epub', '.rar', 'nexusstc', 'lgli']):
                        # Skip very long strings (likely descriptions)
                        if len(text) < 80:
                            author_str = text
                            break

            # Find File Info - Extract year and extension
            year = ""
            extension = ""
            
            for div in row.find_all('div'):
                text = div.get_text(strip=True)
                if '·' in text and any(x in text.upper() for x in ['MB', 'KB', 'PDF', 'EPUB', 'MOBI', 'CBZ']):
                    if "Save" in text:
                        text = text.split("Save")[0]
                    
                    text = text.replace("✅", "").strip()
                    parts = [p.strip() for p in text.split('·')]
                    
                    for p in parts:
                        # Extract file extension (PDF, EPUB, MOBI, etc.)
                        p_upper = p.upper()
                        if any(ext in p_upper for ext in ['PDF', 'EPUB', 'MOBI', 'CBZ', 'AZW', 'DJVU']):
                            extension = p.strip()
                        # Extract year (4 digit number between 1900-2099)
                        if p.strip().isdigit() and len(p.strip()) == 4:
                            yr = int(p.strip())
                            if 1900 <= yr <= 2099:
                                year = p.strip()
                    break
                    
            seen_md5s.add(md5)
            results.append({
                'title': title,
                'author': author_str,
                'md5': md5,
                'year': year,
                'extension': extension
            })
            
            if len(results) >= 10:
                break
                
        except Exception as e:
            logger.warning(f"Error parsing row: {e}")
            continue

    return results

def get_download_links(md5):
    domain = find_working_domain()
    if not domain:
        return {}
        
    url = f"https://{domain}/md5/{md5}"
    try:
        response = requests.get(url, headers=HEADERS, verify=False)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"MD5 fetch failed: {e}")
        return {}
    
    soup = BeautifulSoup(response.text, 'html.parser')
    links = {}
    
    # User requested ONLY "Slow Partner Servers"
    # Found in <a href="/slow_download/..." ...>Slow Partner Server ...</a>
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        
        if '/slow_download/' in href:
            if "Slow Partner Server" in text:
                 name = text
                 # Make sure it is absolute URL
                 if href.startswith('/'):
                     href = f"https://{domain}{href}"
                 links[name] = href

    return links

if __name__ == "__main__":
    # Test run
    print("Testing connection...")
    dom = find_working_domain()
    print(f"Domain: {dom}")
    if dom:
        print("Searching for 'Python'...")
        res = search_books("Python")
        for r in res:
            print(r)
            
        if res:
            first_md5 = res[0]['md5']
            print(f"Fetching links for {first_md5}...")
            lnks = get_download_links(first_md5)
            print(lnks)
