# 🏛️ eCourts PDF Downloading Automation Tool

Automates the scraping of court order PDFs from [eCourts India](https://services.ecourts.gov.in/) using browser automation, OCR-based CAPTCHA solving, and structured HTTP downloads.

## 📁 Project Structure

```bash
claw_assignment/
├── .gitignore       # Ignored files config
├── download_pdfs.py # PDF downloading script
├── requirements.txt # Python dependencies
├── start_browser_n_search.py # Main automation script
├── README.md        # You're here!
```

## ⚙️ Requirements

- Python **3.8+**
- **Tesseract OCR** installed and added to system PATH
- **Google Chrome or Chromium** (Playwright uses Chromium by default)

## 🧰 Setup Instructions (All Platforms)

### 1. Clone the Repository

```bash
git clone https://github.com/asparsh607/claw_assignment.git
cd claw_assignment
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Tesseract OCR

**Windows**
- Download from: [github.com/tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract)
- Add Tesseract directory to your system PATH

**macOS**
```bash
brew install tesseract
```

**Linux (Ubuntu/Debian)**
```bash
sudo apt update
sudo apt install tesseract-ocr
```

### 4. Install Playwright and its Browsers

```bash
playwright install chromium
```

## 🚀 How to Use

### Step 1: Launch Automation Script

```bash
python start_browser_n_search.py --state_code 17 --district_code 13 --complex_code 1170038@10,26@N --from_date 01-05-2024 --to_date 10-05-2024
```

This automates the browser, solves CAPTCHA, and collects metadata. It stores information in `data.txt` and then downloads all order PDFs listed in `data.txt` into the `pdf/` folder.

## 📝 Notes

- The `data.txt` file stores court order IDs and cookies captured from the browser session.
- CAPTCHA solving uses Tesseract OCR. Success may vary depending on image quality.
- Re-run the browser script if CAPTCHA fails or no results are fetched.

## 🧪 Sample Command Breakdown

```bash
python start_browser_n_search.py \
  --state_code 17 \
  --district_code 13 \
  --complex_code 1170038@10,26@N \
  --from_date 01-05-2024 \
  --to_date 10-05-2024
```

## 📦 Key Dependencies

- **playwright** – browser automation
- **pytesseract** – OCR for CAPTCHA solving
- **httpx** – HTTP client
- **Pillow** – image manipulation
- **tqdm** – progress bars

## 📄 License

This project is intended for educational and research use only. Please use responsibly and respect legal and ethical boundaries.

## 🙌 Acknowledgments

Inspired by public legal access efforts and automation tooling.
