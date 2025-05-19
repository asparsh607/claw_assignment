import re
import os
import json
import time
import asyncio
import httpx
from urllib.parse import urlparse, parse_qs
from tqdm.asyncio import tqdm_asyncio

# Extract data from data.txt
def main():
    pdf_pattern = r"onclick=displayPdf\('([^']+)'\)"
    app_token_pattern = r'"app_token"\s*:\s*"([a-f0-9]{64})"'
    cookie_pattern = r"'name':\s*'(JSESSION|SERVICES_SESSID)'.*?'value':\s*'([^']*)'"

    BASE_URL = "https://services.ecourts.gov.in/ecourtindia_v6/"

    with open('data.txt', 'r', encoding='utf-8') as f:
        d = f.read()

    cookie_matches = re.findall(cookie_pattern, d)
    pdf_matches = re.findall(pdf_pattern, d)
    token_matches = re.findall(app_token_pattern, d)

    data = {'pdf_url':[], 'token':[], 'cookies': {}}

    if cookie_matches:
        cookie_dict = {name: value for name, value in cookie_matches}
        data['cookies'] = cookie_dict
    else:
        print('no cookies found, please rerun the script')

    if pdf_matches:
        for match in pdf_matches:
            url = f"{BASE_URL}?p=" + match
            data['pdf_url'].append(url.replace('\\/', '/'))
    else:
        print('no pdf found, please rerun the script')

    if token_matches:
        for match in token_matches:
            data['token'].append(match)
    else:
        print('no token found, please rerun the script')

    return data

# Headers for POST
HEADERS_POST = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://services.ecourts.gov.in",
    "Pragma": "no-cache",
    "Referer": "https://services.ecourts.gov.in/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Ch-Ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"'
}

# Headers for GET
HEADERS_GET = {
    "User-Agent": HEADERS_POST["User-Agent"],
    "Referer": HEADERS_POST["Referer"],
    "Accept": "application/pdf",
    "Accept-Encoding": HEADERS_POST["Accept-Encoding"],
    "Accept-Language": HEADERS_POST["Accept-Language"],
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

def extract_case_val(url: str) -> str:
    parsed = parse_qs(urlparse(url).query)
    case_val = parsed.get('case_val', ['unknown'])[0]
    return case_val.replace("~", "_").replace("/", "_") + ".pdf"

async def fetch_pdf(session_id: str, jsession: str, filename: str, pdf_path: str, client: httpx.AsyncClient):
    url = f"https://services.ecourts.gov.in/ecourtindia_v6/reports/{session_id}.pdf"
    cookies = {
        "SERVICES_SESSID": session_id,
        "JSESSION": jsession
    }
    try:
        response = await client.get(url, headers=HEADERS_GET, cookies=cookies)
        if response.status_code == 200 and response.headers.get("Content-Type") == "application/pdf":
            with open(os.path.join(pdf_path, filename), "wb") as f:
                f.write(response.content)
            print(f"✅ PDF downloaded: {filename}")
        else:
            print(f"❌ Failed to download PDF ({filename}). Status: {response.status_code}, Type: {response.headers.get('Content-Type')}")
    except Exception as e:
        print(f"❌ Exception during GET for {filename}: {e}")

async def async_download(data, pdf_path):
    urls = data['pdf_url']
    token = data['token'][0]
    cookies = data['cookies']

    async with httpx.AsyncClient() as client:
        for i, url in enumerate(tqdm_asyncio(urls, desc="Processing PDFs")):
            filename = extract_case_val(url)
            print(f"\n📄 Processing [{i+1}/{len(urls)}] - {filename}")

            payload = f"&ajax_req=true&app_token={token}"
            try:
                response = await client.post(url, headers=HEADERS_POST, cookies=cookies, content=payload)
                print(f"📬 POST Status: {response.status_code}")
            except Exception as e:
                print(f"❌ POST request failed for {filename}: {e}")
                continue

            if response.status_code != 200:
                continue

            try:
                parsed_json = json.loads(response.text)
                new_token = parsed_json.get("app_token")
                order_html = parsed_json.get("order", "")

                match = re.search(r'reports\\?/([a-z0-9]+)\.pdf', order_html)
                if not match:
                    print("❌ Could not extract PDF session ID.")
                    continue
                session_id = match.group(1)
            except Exception as e:
                print(f"❌ Error parsing POST response for {filename}: {e}")
                continue

            await fetch_pdf(session_id=session_id, jsession=cookies["JSESSION"], filename=filename, pdf_path=pdf_path, client=client)

            if new_token:
                token = new_token
            await asyncio.sleep(1)

def download_pdfs():
    cur_dir = os.getcwd()
    pdf_path = os.path.join(cur_dir, 'pdf')
    os.makedirs(pdf_path, exist_ok=True)

    data = main()

    async def runner():
        await async_download(data, pdf_path)

    try:
        asyncio.run(runner())
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            import nest_asyncio
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(runner())
        raise

