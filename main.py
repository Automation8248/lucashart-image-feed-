import os
import json
import requests
import textwrap
import shutil
import time
from PIL import Image, ImageDraw, ImageFont

# --- GLOBAL CONFIGURATION ---
PIXABAY_KEY = os.getenv('PIXABAY_KEY')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
IS_MANUAL = os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch'

CONFIG = [
    {
        "id": "nature",
        "type": "folder",
        "folder_path": "content/nature",
        "token": os.getenv('TELEGRAM_TOKEN_NATURE'),
        "webhook": os.getenv('WEBHOOK_NATURE'),
        "seo": "🌿 Nature Vibes. #Nature #Earth #Peace #Wilderness",
    },
    {
        "id": "wildsnap",
        "type": "folder",
        "folder_path": "content/wildsnap",
        "token": os.getenv('TELEGRAM_TOKEN_WILDSNAP'),
        "webhook": os.getenv('WEBHOOK_WILDSNAP'),
        "seo": "🦁 Wild World. #WildSnap #Wildlife #Animals #NaturePhotography",
    },
    {
        "id": "motivation",
        "type": "generated",
        "token": os.getenv('TELEGRAM_TOKEN_MOTIVATION'),
        "webhook": os.getenv('WEBHOOK_MOTIVATION'),
        "seo": "💡 Daily Wisdom. #Motivation #LucasHart #Zen #Inspiration",
    }
]

def get_font():
    font_path = "arial_style.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
        r = requests.get(url)
        with open(font_path, "wb") as f:
            f.write(r.content)
    return font_path

def create_motivation_image():
    """Generates Optimized 1080x1350 Image"""
    try:
        # 1. Get Quote
        quote_data = requests.get("https://zenquotes.io/api/random", timeout=10).json()[0]
        quote_text = f'"{quote_data["q"]}"'
        author_text = "- Lucas Hart"

        # 2. Get Background (Use 'webformatURL' for speed instead of huge 'largeImageURL')
        pix_url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q=nature+dark+forest&image_type=photo&orientation=vertical&per_page=3"
        pix_data = requests.get(pix_url, timeout=10).json()
        bg_url = pix_data['hits'][0]['webformatURL'] # <-- FASTER DOWNLOAD
        
        with open("temp_bg.jpg", "wb") as f:
            f.write(requests.get(bg_url, timeout=20).content)
        
        # 3. Process Image
        img = Image.open("temp_bg.jpg").convert("RGB")
        target_size = (1080, 1350)
        
        # Fast Resize
        img = img.resize(target_size, Image.Resampling.LANCZOS)

        # Overlay
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 110))
        img.paste(overlay, (0, 0), overlay)
        
        # Text
        draw = ImageDraw.Draw(img)
        font_path = get_font()
        font_quote = ImageFont.truetype(font_path, 55)
        font_author = ImageFont.truetype(font_path, 35)

        lines = textwrap.wrap(quote_text, width=22)
        total_text_height = (len(lines) * 65) + 60
        y_text = (target_size[1] - total_text_height) / 2

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_quote)
            w = bbox[2] - bbox[0]
            draw.text(((target_size[0] - w) / 2, y_text), line, font=font_quote, fill=(255, 255, 255))
            y_text += 65
        
        y_text += 20
        bbox = draw.textbbox((0, 0), author_text, font=font_author)
        w = bbox[2] - bbox[0]
        draw.text(((target_size[0] - w) / 2, y_text), author_text, font=font_author, fill=(255, 255, 255))

        final_path = "final_post.jpg"
        # Optimize & Compress (Quality 85 makes it much smaller & faster to upload)
        img.save(final_path, optimize=True, quality=85) 
        return final_path
    except Exception as e:
        print(f"❌ Image Gen Error: {e}")
        return None

def get_file_from_folder(folder_path):
    if not os.path.exists(folder_path): return None
    files = [f for f in sorted(os.listdir(folder_path)) if not f.startswith('.')]
    if not files: return None
    return os.path.join(folder_path, files[0])

def upload_to_catbox(file_path):
    """Upload with Timeout & Error Check"""
    try:
        url = "https://catbox.moe/user/api.php"
        payload = {'reqtype': 'fileupload'}
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        print(f"   📂 Uploading {file_size:.2f} MB file...")
        
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': f}
            # 60s timeout taaki hang na ho
            r = requests.post(url, data=payload, files=files, timeout=60)
        
        if r.status_code == 200 and "http" in r.text:
            return r.text
        else:
            print(f"   ❌ Catbox Error: {r.text}")
            return None
    except Exception as e: 
        print(f"   ❌ Upload Exception: {e}")
        return None

def send_content(token, webhook, file_url, caption):
    # CRASH FIX: Agar URL nahi hai to yahi ruk jao
    if not file_url:
        print("   ⚠️ No URL to send. Skipping Telegram/Webhook.")
        return

    if token and CHAT_ID:
        try:
            api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
            if file_url.endswith(('.mp4', '.mov', '.avi')):
                api_url = f"https://api.telegram.org/bot{token}/sendVideo"
                payload = {"chat_id": CHAT_ID, "video": file_url, "caption": caption}
            else:
                payload = {"chat_id": CHAT_ID, "photo": file_url, "caption": caption}
            requests.post(api_url, json=payload, timeout=10)
        except Exception as e: print(f"   Telegram Error: {e}")
    
    if webhook:
        try:
            data = {"content": f"{caption}\n{file_url}"}
            requests.post(webhook, json=data, timeout=5)
        except: pass

def process_topic(topic_data):
    print(f"🚀 Processing Topic: {topic_data['id']}")
    
    file_path = None
    file_to_delete = None

    if topic_data['type'] == 'folder':
        file_path = get_file_from_folder(topic_data['folder_path'])
        file_to_delete = file_path
    else:
        file_path = create_motivation_image()
        
    if not file_path:
        print(f"   ❌ No content found for {topic_data['id']}")
        return

    # Upload
    catbox_url = upload_to_catbox(file_path)
    
    # CRASH FIX: Check if upload succeeded
    if catbox_url:
        print(f"   ✅ Uploaded: {catbox_url}")
        send_content(topic_data['token'], topic_data['webhook'], catbox_url, topic_data['seo'])

        # Cleanup only if success
        if topic_data['type'] == 'folder' and file_to_delete:
            os.remove(file_to_delete)
            print("   🗑️ File deleted from folder")
        elif topic_data['type'] == 'generated':
            os.remove(file_path)
    else:
        print("   ⚠️ Upload failed. Keeping file for retry.")

def main():
    if not os.path.exists('state.json'):
        with open('state.json', 'w') as f: json.dump({"current_index": 0}, f)
    with open('state.json', 'r') as f: state = json.load(f)

    if IS_MANUAL:
        print("🔧 MANUAL MODE: Posting ALL 3 Topics...")
        for topic in CONFIG:
            process_topic(topic)
    else:
        print("⏰ AUTO MODE: Posting Single Rotated Topic...")
        idx = state['current_index']
        process_topic(CONFIG[idx])
        
        next_idx = (idx + 1) % len(CONFIG)
        state['current_index'] = next_idx
        with open('state.json', 'w') as f: json.dump(state, f)

if __name__ == "__main__":
    main()
