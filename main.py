import os
import requests
import textwrap
import json
import time
import io
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION ---
PIXABAY_KEY = os.getenv('PIXABAY_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN_MOTIVATION')
WEBHOOK_URL = os.getenv('WEBHOOK_MOTIVATION')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HISTORY_FILE = "history.txt"
FIXED_AUTHOR = "- Lucas Hart"

def get_font():
    """Download Arial-style font (Roboto) for the action runner"""
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
        # 1. History Check (Repetition avoid karne ke liye)
        used_quotes = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f: used_quotes = f.read().splitlines()

        # 2. Get Unique Quote (ZenQuotes API)
        quote_text = ""
        for _ in range(5):
            res = requests.get("https://zenquotes.io/api/random", timeout=5).json()[0]
            if res['q'] not in used_quotes:
                quote_text = f'"{res["q"]}"'
                raw_q = res['q']
                break
        if not quote_text: return None

        # 3. Get Valid Background from Pixabay (Fixing 'Unknown Format' error)
        p_url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q=nature+dark+landscape&orientation=vertical&image_type=photo&per_page=15"
        pix_data = requests.get(p_url, timeout=5).json()
        
        final_img = None
        for hit in pix_data['hits']:
            try:
                # Webformat use kar rahe hain fast download ke liye
                img_res = requests.get(hit['webformatURL'], timeout=10)
                # Image validation check
                test_img = Image.open(io.BytesIO(img_res.content))
                test_img.verify() 
                final_img = Image.open(io.BytesIO(img_res.content)).convert("RGB")
                break 
            except:
                continue 

        if not final_img: return None
        
        # 4. Merging Logic (Image + Quote)
        # Resize to Instagram Portrait size (1080x1350)
        final_img = final_img.resize((1080, 1350), Image.Resampling.LANCZOS)
        
        # Dark Overlay for text visibility
        overlay = Image.new('RGBA', final_img.size, (0, 0, 0, 150))
        final_img.paste(overlay, (0, 0), overlay)
        
        draw, font_p = ImageDraw.Draw(final_img), get_font()
        f_quote = ImageFont.truetype(font_p, 55) if font_p else ImageFont.load_default()
        f_author = ImageFont.truetype(font_p, 35) if font_p else ImageFont.load_default()
        
        # Wrap Text
        lines = textwrap.wrap(quote_text, width=22)
        y = (1350 - (len(lines) * 75)) / 2
        
        # Draw White Quote Text
        for line in lines:
            w = draw.textbbox((0, 0), line, font=f_quote)[2]
            draw.text(((1080 - w) / 2, y), line, font=f_quote, fill="white")
            y += 75
        
        # Draw Fixed Author Name (Lucas Hart)
        y += 30
        w_auth = draw.textbbox((0, 0), FIXED_AUTHOR, font=f_author)[2]
        draw.text(((1080 - w_auth) / 2, y), FIXED_AUTHOR, font=f_author, fill="white")
        
        # Save Optimized Image
        final_img.save("post.jpg", optimize=True, quality=80)

        # Update History File
        with open(HISTORY_FILE, "a") as f: f.write(raw_q + "\n")
        return "post.jpg"
        
    except Exception as e:
        print(f"❌ Processing Error: {e}")
        return None

def main():
    path = create_motivation_image()
    if not path:
        print("❌ Image creation failed.")
        return

    # Catbox.moe Upload
    url = None
    try:
        with open(path, 'rb') as f:
            r = requests.post("https://catbox.moe/user/api.php", 
                            data={'reqtype': 'fileupload'}, 
                            files={'fileToUpload': f}, timeout=25)
            if "http" in r.text: url = r.text
    except: pass

    if url:
        print(f"✅ Post Link: {url}")
        caption = "💡 Daily Motivation. #Inspiration #LucasHart"
        
        # Send to Telegram
        if TELEGRAM_TOKEN and CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", 
                         json={"chat_id": CHAT_ID, "photo": url, "caption": caption})
        
        # Send to Webhook
        if WEBHOOK_URL:
            requests.post(WEBHOOK_URL, json={"content": f"{caption}\n{url}"})
    else:
        print("❌ Upload to Catbox failed.")

if __name__ == "__main__":
    main()
