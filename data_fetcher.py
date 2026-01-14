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
            # Find Title
            # Title link usually has href starting with /md5/ and class text-[#2563eb] or similar highlighting
            title_link = row.find('a', href=lambda h: h and '/md5/' in h and row.find('div', class_='text-[#2563eb]') is None)
            
            # Refined title finder: Look for the specific class used for titles
            # "custom-a text-[#2563eb] ... text-lg font-semibold"
            for a in row.find_all('a', href=True):
                if '/md5/' in a['href'] and 'text-lg' in a.get('class', []):
                    title_link = a
                    break
            
            if not title_link:
                continue
                
            md5 = title_link['href'].split('/md5/')[1]
            if md5 in seen_md5s:
                continue
            
            title = title_link.get_text(strip=True)
            
            # Find Author
            # Usually the next link after title, or a link with /search?q=
            author_str = "Unknown Author"
            # Look for the author link which comes after the title
            # In the sample: <a href="/search?q=..." ...> ... J. K. Rowling ... </a>
            # We can find all links with /search?q= and pick the first one that is likely the author
            author_links = []
            for a in row.find_all('a', href=True):
                if '/search?q=' in a['href'] and a != title_link:
                     author_links.append(a.get_text(strip=True))
            
            if author_links:
                author_str = author_links[0] # The first one is usually the author

            # Find File Info
            # In the sample: <div class="text-gray-800 dark:text-slate-400 font-semibold text-sm leading-[1.2] mt-2">✅ English [en] · EPUB · 0.7MB · 2015 ...
            # We can target this specific div by its classes or content
            file_info = "Unknown Format"
            
            # Strategy: look for a div that contains common file extensions or size units
            # Or use the specific class string if consistent
            # "text-gray-800 dark:text-slate-400 font-semibold text-sm leading-[1.2] mt-2"
            
            # Let's find the div that contains a dot separator '·' and maybe 'MB' or 'KB'
            for div in row.find_all('div'):
                text = div.get_text(strip=True)
                if '·' in text and any(x in text for x in ['MB', 'KB', 'pdf', 'epub']):
                    # Clean up the text. It might contain "Save" or other buttons.
                    # We only want the format info part.
                    # Example text: "✅ English [en] · EPUB · 0.7MB · 2015 · 📕 Book (fiction) · 🚀/nexusstc/upload/zlib · Save"
                    
                    # Split by '·' and take the relevant parts?
                    # Or just take the whole string but truncate before "Save"
                    if "Save" in text:
                        text = text.split("Save")[0]
                        
                    # Remove "✅" and extra spaces
                    text = text.replace("✅", "").strip()
                    
                    # Try to keep just Language, Format, Size
                    # This is subjective, but let's try to be concise
                    parts = [p.strip() for p in text.split('·')]
                    # Filter out empty or "Book" or "upload" related noise if desired, but user just said "simple".
                    # Let's keep it relatively clean.
                    clean_parts = []
                    for p in parts:
                        if not any(x in p for x in ['🚀', 'Book', 'upload', 'nexusstc', 'zlib']):
                            clean_parts.append(p)
                    
                    file_info = " · ".join(clean_parts)
                    break
                    
            seen_md5s.add(md5)
            results.append({
                'title': title,
                'author': author_str,
                'md5': md5,
                'file_info': file_info
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
