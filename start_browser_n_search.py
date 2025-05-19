import argparse
import logging
import os
import time
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from typing import Optional
from playwright.sync_api import sync_playwright
from download_pdfs import download_pdfs


def setup_logger(name: str = 'ecourt') -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger


logger = setup_logger("ecourt_debug")


def solve_and_submit_captcha(page, logger, max_attempts=5) -> bool:
    for attempt in range(max_attempts):
        logger.info(f"[CAPTCHA Attempt] {attempt + 1}/{max_attempts}")

        captcha_element = page.get_by_role("img", name="CAPTCHA Image")
        captcha_path = "captcha.png"
        captcha_element.screenshot(path=captcha_path)

        captcha_text = solve_captcha_image(logger, captcha_path)
        if not captcha_text:
            logger.warning("[CAPTCHA] OCR returned no text, retrying...")
            continue

        page.get_by_role("textbox", name="Enter Captcha").fill(captcha_text)
        page.get_by_role("button", name="Go").click()
        logger.info("[CAPTCHA] Submitted, waiting for response...")

        with page.expect_response(
            lambda response: response.request.method == "POST" and "/actsearchbyorddate.do" in response.url,
            timeout=10000
        ) as resp_info:
            response = resp_info.value
            try:
                json_data = response.json()
                if json_data.get("status") == 0 and "Invalid Captcha" in json_data.get("errormsg", ""):
                    logger.warning("[CAPTCHA] Server says: Invalid Captcha. Retrying...")
                    time.sleep(1)
                    continue
                else:
                    logger.info("[CAPTCHA] Server accepted CAPTCHA.")
                    return True
            except Exception as e:
                logger.error(f"[CAPTCHA] Error parsing response: {e}")
                return False

    logger.error("[CAPTCHA] All attempts failed.")
    return False


def solve_captcha_image(logger: logging.Logger, image_path: str, max_retries: int = 3, type_of_captcha: str = 'common') -> Optional[str]:
    logger.info(f"[CAPTCHA] Solving image: {image_path}")
    if not os.path.isfile(image_path) or os.path.getsize(image_path) < 100:
        raise FileNotFoundError(f"Invalid CAPTCHA image: {image_path}")

    image = Image.open(image_path).convert("L")

    def preprocess(img, attempt):
        if attempt == 0:
            return img
        elif attempt == 1:
            return img.point(lambda x: 0 if x < 128 else 255)
        elif attempt == 2:
            return ImageOps.invert(img).filter(ImageFilter.MedianFilter())
        return img

    for attempt in range(max_retries):
        try:
            processed = preprocess(image, attempt)
            raw_text = pytesseract.image_to_string(processed)
            cleaned = raw_text.strip().replace(" ", "").replace("\n", "")
            logger.debug(f"[OCR Attempt {attempt + 1}] Raw='{raw_text.strip()}' → Cleaned='{cleaned}'")
            if cleaned:
                logger.info(f"[CAPTCHA] Solved: {cleaned}")
                return cleaned
        except Exception as e:
            logger.warning(f"[OCR] Tesseract error on attempt {attempt + 1}: {e}")
        time.sleep(0.5)

    logger.error("[CAPTCHA] All OCR attempts failed.")
    return None


def handle_post_response(response):
    try:
        request = response.request
        if request.method == "POST":
            logger.info(f"[POST RESPONSE] {response.status} {response.url}")
            content_type = response.headers.get("content-type", "")
            try:
                cookies = response.frame.page.context.cookies()
                filtered_cookies = [c for c in cookies if "services.ecourts" in c.get("domain", "")]

                logger.info("[FILTERED COOKIES for 'ecourts.gov.in']")
                for cookie in filtered_cookies:
                    logger.info(f"{cookie['name']} = {cookie['value']}")
            except Exception as e:
                logger.error(f"[ERROR getting cookies] {e}")

            if "application/json" in content_type:
                logger.debug(f"[JSON] {response.json()}")
            else:
                body = response.text()
                with open('data.txt', 'w', encoding='utf-8') as f:
                    f.write(str(cookies) + '\n' + body)
                input("Enter a key to close browser....")
    except Exception as e:
        logger.error(f"[ERROR handling response] {e}")


def run(state_code: str, district_code: str, complex_code: str, from_date: str, to_date: str):
    logger = logging.getLogger("CAPTCHA")
    logging.basicConfig(level=logging.INFO)

    with sync_playwright() as p:
        # Step 1: Launch browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        logger.info("[STEP 1] Navigating to eCourts site...")
        page.goto("https://services.ecourts.gov.in/ecourtindia_v6/")
        time.sleep(5)

        # Step 2: Click "Court Orders"
        logger.info("[STEP 2] Clicking 'Court Orders'...")
        page.get_by_role("link", name="Court Orders menu Court Orders").click()
        time.sleep(3)

        # Step 3: Close modal if it appears
        logger.info("[STEP 3] Checking for modal...")
        if page.locator(".modal-header").first.is_visible():
            page.get_by_role("button", name="Close").click()
            logger.info("[STEP 3] Modal closed.")

        # Step 4: Select court location
        logger.info("[STEP 4] Selecting court options...")
        page.locator("#sess_state_code").select_option(state_code)
        page.locator("#sess_dist_code").select_option(district_code)
        page.locator("#court_complex_code").select_option(complex_code)

        # Step 5: Fill date and radio
        logger.info("[STEP 5] Entering date range...")
        page.get_by_role("tab", name="Order Date").click()
        page.get_by_role("textbox", name="*From Date").fill(from_date)
        page.get_by_role("textbox", name="*To Date").fill(to_date)
        page.get_by_role("radio", name="Both").check()

        # Step 6: Solve CAPTCHA
        logger.info("[STEP 6] Solving CAPTCHA...")
        captcha_element = page.get_by_role("img", name="CAPTCHA Image")
        captcha_element.wait_for(state="visible", timeout=10000)
        time.sleep(3)
        captcha_path = "captcha.png"
        captcha_element.screenshot(path=captcha_path)

        captcha_text = solve_captcha_image(logger, captcha_path)
        if not captcha_text:
            logger.error("[STEP 6] CAPTCHA solving failed.")
            return

        page.get_by_role("textbox", name="Enter Captcha").fill(captcha_text)

        # Step 7: Expect response and submit
        logger.info("[STEP 7] Submitting form and waiting for response...")
        with page.expect_response(lambda r: r.request.method == "POST" and "submitOrderDate" in r.url, timeout=10000) as resp_info:
            page.get_by_role("button", name="Go").click()

        # Step 8: Process response
        response = resp_info.value
        logger.info(f"[STEP 8] Response received: {response.status} {response.url}")

        try:
            cookies = context.cookies()
            filtered = [c for c in cookies if "ecourtindia_v6" in c.get("path", "")]
            logger.info("[COOKIES] Filtered ecourts cookies:")
            for cookie in filtered:
                logger.info(f"{cookie['name']} = {cookie['value']}")

            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                data = response.json()
                logger.debug(f"[RESPONSE JSON] {data}")
            else:
                with open("data.txt", "w", encoding="utf-8") as f:
                    f.write(str(filtered) + "\n" + response.text())
        except Exception as e:
            logger.error(f"[STEP 8] Error processing response: {e}")

        # Step 9: Keep browser open for further tasks
        logger.info("[STEP 9] Downloading pdfs.")
        download_pdfs()

        # Step 10: Cleanup
        logger.info("[STEP 10] Closing browser.")
        context.close()
        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run script with parameters.")

    parser.add_argument("--state_code", required=True, help="State code, e.g., 17")
    parser.add_argument("--district_code", required=True, help="District code, e.g., 13")
    parser.add_argument("--complex_code", required=True, help="Complex code, e.g., 1170038@10,26@N")
    parser.add_argument("--from_date", required=True, help="From date in DD-MM-YYYY format")
    parser.add_argument("--to_date", required=True, help="To date in DD-MM-YYYY format")

    args = parser.parse_args()

    run(args.state_code, args.district_code, args.complex_code, args.from_date, args.to_date)