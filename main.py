import os
import requests
import textwrap
import json
import time
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION ---
PIXABAY_KEY = os.getenv('PIXABAY_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN_MOTIVATION')
WEBHOOK_URL = os.getenv('WEBHOOK_MOTIVATION')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HISTORY_FILE = "history.txt"

def get_font():
    font_path = "font.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
        try:
            r = requests.get(url, timeout=5)
            with open(font_path, "wb") as f: f.write(r.content)
        except: return None
    return font_path

def create_motivation_image():
    try:
        # 1. History Check
        used_quotes = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f: used_quotes = f.read().splitlines()

        # 2. Get Unique Quote
        quote_data = None
        for _ in range(5):
            res = requests.get("https://zenquotes.io/api/random", timeout=5).json()[0]
            if res['q'] not in used_quotes:
                quote_data = res
                break
        if not quote_data: return None

        # 3. Get Background (Ensuring JPG format for no errors)
        p_url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q=nature+dark&orientation=vertical&image_type=photo&per_page=10"
        pix_data = requests.get(p_url, timeout=5).json()
        
        # Filter only JPG/JPEG links
        bg_url = None
        for hit in pix_data['hits']:
            if hit['webformatURL'].lower().endswith(('.jpg', '.jpeg')):
                bg_url = hit['webformatURL']
                break
        
        if not bg_url: return None
        
        # Download BG
        with open("bg.jpg", "wb") as f: f.write(requests.get(bg_url, timeout=10).content)
        
        # 4. Image Processing (Fast)
        img = Image.open("bg.jpg").convert("RGB").resize((1080, 1350))
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 150))
        img.paste(overlay, (0, 0), overlay)
        
        draw, font_p = ImageDraw.Draw(img), get_font()
        f_quote = ImageFont.truetype(font_p, 55) if font_p else ImageFont.load_default()
        
        lines = textwrap.wrap(f'"{quote_data["q"]}"', width=22)
        y = (1350 - (len(lines) * 75)) / 2
        for line in lines:
            w = draw.textbbox((0, 0), line, font=f_quote)[2]
            draw.text(((1080 - w) / 2, y), line, font=f_quote, fill="white")
            y += 75
        
        # Author Name
        f_author = ImageFont.truetype(font_p, 35) if font_p else ImageFont.load_default()
        w_auth = draw.textbbox((0, 0), "- Lucas Hart", font=f_author)[2]
        draw.text(((1080 - w_auth) / 2, y + 30), "- Lucas Hart", font=f_author, fill="white")
        
        img.save("post.jpg", optimize=True, quality=80)

        # 5. Update History
        with open(HISTORY_FILE, "a") as f: f.write(quote_data['q'] + "\n")
        return "post.jpg"
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    path = create_motivation_image()
    if not path: return

    # Catbox Upload (with retry logic)
    url = None
    for _ in range(2):
        try:
            with open(path, 'rb') as f:
                r = requests.post("https://catbox.moe/user/api.php", data={'reqtype': 'fileupload'}, files={'fileToUpload': f}, timeout=20)
                if "http" in r.text:
                    url = r.text
                    break
        except: time.sleep(2)

    if url:
        print(f"✅ Posted: {url}")
        cap = "💡 Daily Wisdom. #Motivation #LucasHart"
        if TELEGRAM_TOKEN and CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": CHAT_ID, "photo": url, "caption": cap}, timeout=10)
        if WEBHOOK_URL:
            requests.post(WEBHOOK_URL, json={"content": f"{cap}\n{url}"}, timeout=5)

if __name__ == "__main__":
    main()
