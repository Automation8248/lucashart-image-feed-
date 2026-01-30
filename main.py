import os
import json
import requests
import textwrap
import time
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION ---
PIXABAY_KEY = os.getenv('PIXABAY_KEY')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
IS_MANUAL = os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch'

CONFIG = [
    {"id": "nature", "type": "folder", "folder_path": "content/nature", "token": os.getenv('TELEGRAM_TOKEN_NATURE'), "webhook": os.getenv('WEBHOOK_NATURE'), "seo": "🌿 Nature Vibes. #Nature #Earth"},
    {"id": "wildsnap", "type": "folder", "folder_path": "content/wildsnap", "token": os.getenv('TELEGRAM_TOKEN_WILDSNAP'), "webhook": os.getenv('WEBHOOK_WILDSNAP'), "seo": "🦁 Wild World. #WildSnap #Wildlife"},
    {"id": "motivation", "type": "generated", "token": os.getenv('TELEGRAM_TOKEN_MOTIVATION'), "webhook": os.getenv('WEBHOOK_MOTIVATION'), "seo": "💡 Daily Wisdom. #Motivation #LucasHart"}
]

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
    """Super fast 1080x1350 generation using thumbnails"""
    try:
        # Quote fetch
        q_data = requests.get("https://zenquotes.io/api/random", timeout=5).json()[0]
        quote_text, author_text = f'"{q_data["q"]}"', "- Lucas Hart"

        # Pixabay - Using 'webformatURL' for extreme speed (under 500kb)
        p_url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q=nature+dark&orientation=vertical&per_page=3"
        pix_data = requests.get(p_url, timeout=5).json()
        bg_url = pix_data['hits'][0]['webformatURL']
        
        # Download & Save BG
        with open("bg.jpg", "wb") as f: f.write(requests.get(bg_url, timeout=10).content)
        
        # Image Processing
        img = Image.open("bg.jpg").convert("RGB").resize((1080, 1350))
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 130))
        img.paste(overlay, (0, 0), overlay)
        
        draw, font_p = ImageDraw.Draw(img), get_font()
        f_quote = ImageFont.truetype(font_p, 55) if font_p else ImageFont.load_default()
        
        lines = textwrap.wrap(quote_text, width=22)
        y = (1350 - (len(lines) * 70)) / 2
        for line in lines:
            w = draw.textbbox((0, 0), line, font=f_quote)[2]
            draw.text(((1080 - w) / 2, y), line, font=f_quote, fill="white")
            y += 70
        
        img.save("post.jpg", optimize=True, quality=80) # High compression for fast upload
        return "post.jpg"
    except Exception as e:
        print(f"❌ Motivation Error: {e}")
        return None

def upload_to_catbox(file_path):
    """Fast upload with short timeout"""
    try:
        url = "https://catbox.moe/user/api.php"
        with open(file_path, 'rb') as f:
            # 20s timeout taaki total run time 1:20 se upar na jaye
            r = requests.post(url, data={'reqtype': 'fileupload'}, files={'fileToUpload': f}, timeout=20)
        return r.text if "http" in r.text else None
    except: return None

def send_content(token, webhook, url, caption):
    if not url: return
    if token and CHAT_ID:
        try:
            mode = "sendVideo" if url.endswith(('.mp4', '.mov')) else "sendPhoto"
            key = "video" if mode == "sendVideo" else "photo"
            requests.post(f"https://api.telegram.org/bot{token}/{mode}", json={"chat_id": CHAT_ID, key: url, "caption": caption}, timeout=10)
        except: pass
    if webhook:
        try: requests.post(webhook, json={"content": f"{caption}\n{url}"}, timeout=5)
        except: pass

def process_topic(topic):
    print(f"🚀 Topic: {topic['id']}")
    path = None
    if topic['type'] == 'folder':
        files = [f for f in sorted(os.listdir(topic['folder_path'])) if not f.startswith('.')]
        if files: path = os.path.join(topic['folder_path'], files[0])
    else:
        path = create_motivation_image()

    if path:
        url = upload_to_catbox(path)
        if url:
            print(f"✅ Link: {url}")
            send_content(topic['token'], topic['webhook'], url, topic['seo'])
            if topic['type'] == 'folder': os.remove(path)
        else: print("⚠️ Catbox Down. Skipping...")

def main():
    if not os.path.exists('state.json'):
        with open('state.json', 'w') as f: json.dump({"current_index": 0}, f)
    with open('state.json', 'r') as f: state = json.load(f)

    if IS_MANUAL:
        for t in CONFIG: process_topic(t)
    else:
        idx = state['current_index']
        process_topic(CONFIG[idx])
        state['current_index'] = (idx + 1) % len(CONFIG)
        with open('state.json', 'w') as f: json.dump(state, f)

if __name__ == "__main__": main()
