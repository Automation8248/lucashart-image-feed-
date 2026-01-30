import os
import json
import requests
import textwrap
import shutil
from PIL import Image, ImageDraw, ImageFont

# --- GLOBAL CONFIGURATION ---
# Common secrets
PIXABAY_KEY = os.getenv('PIXABAY_KEY')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Check if Manual Run or Scheduled
IS_MANUAL = os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch'

# --- TOPIC CONFIGURATION (Here are the missing options) ---
CONFIG = [
    {
        "id": "nature",
        "type": "folder",
        "folder_path": "content/nature",
        # 👇 Specific Token & Webhook for Nature
        "token": os.getenv('TELEGRAM_TOKEN_NATURE'),
        "webhook": os.getenv('WEBHOOK_NATURE'),
        "seo": "🌿 Nature Vibes. #Nature #Earth #Peace #Wilderness",
    },
    {
        "id": "wildsnap",
        "type": "folder",
        "folder_path": "content/wildsnap",
        # 👇 Specific Token & Webhook for WildSnap
        "token": os.getenv('TELEGRAM_TOKEN_WILDSNAP'),
        "webhook": os.getenv('WEBHOOK_WILDSNAP'),
        "seo": "🦁 Wild World. #WildSnap #Wildlife #Animals #NaturePhotography",
    },
    {
        "id": "motivation",
        "type": "generated",
        # 👇 Specific Token & Webhook for Motivation
        "token": os.getenv('TELEGRAM_TOKEN_MOTIVATION'),
        "webhook": os.getenv('WEBHOOK_MOTIVATION'),
        "seo": "💡 Daily Wisdom. #Motivation #LucasHart #Zen #Inspiration",
    }
]

# --- HELPER FUNCTIONS ---

def get_font():
    """Downloads Roboto-Bold (Arial alternative) for White Text"""
    font_path = "arial_style.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
        r = requests.get(url)
        with open(font_path, "wb") as f:
            f.write(r.content)
    return font_path

def create_motivation_image():
    """Generates 1080x1350 Image with Pure White Text"""
    try:
        # 1. Get Content
        quote_data = requests.get("https://zenquotes.io/api/random").json()[0]
        quote_text = f'"{quote_data["q"]}"'
        author_text = "- Lucas Hart"

        # 2. Get Background
        pix_url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q=nature+dark+forest&image_type=photo&orientation=vertical&per_page=3"
        bg_url = requests.get(pix_url).json()['hits'][0]['largeImageURL']
        
        with open("temp_bg.jpg", "wb") as f:
            f.write(requests.get(bg_url).content)
        
        # 3. Process Image (Resize/Crop to 1080x1350)
        img = Image.open("temp_bg.jpg").convert("RGB")
        target_size = (1080, 1350)
        
        # Smart Resize Logic (Fill Strategy)
        img_ratio = img.width / img.height
        target_ratio = target_size[0] / target_size[1]
        
        if img_ratio > target_ratio:
            new_height = target_size[1]
            new_width = int(new_height * img_ratio)
        else:
            new_width = target_size[0]
            new_height = int(new_width / img_ratio)
            
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Center Crop
        left = (img.width - target_size[0]) / 2
        top = (img.height - target_size[1]) / 2
        img = img.crop((left, top, left + target_size[0], top + target_size[1]))

        # 4. Add Dark Overlay (So White Text Pops)
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 110)) # Darker for better visibility
        img.paste(overlay, (0, 0), overlay)
        
        # 5. Draw Text (Pure White)
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
            # Fill = (255, 255, 255) is PURE WHITE
            draw.text(((target_size[0] - w) / 2, y_text), line, font=font_quote, fill=(255, 255, 255))
            y_text += 65
        
        y_text += 20
        bbox = draw.textbbox((0, 0), author_text, font=font_author)
        w = bbox[2] - bbox[0]
        draw.text(((target_size[0] - w) / 2, y_text), author_text, font=font_author, fill=(255, 255, 255))

        final_path = "final_post.jpg"
        img.save(final_path)
        return final_path
    except Exception as e:
        print(f"Error creating image: {e}")
        return None

def get_file_from_folder(folder_path):
    """Pick first file from folder"""
    if not os.path.exists(folder_path): return None
    files = [f for f in sorted(os.listdir(folder_path)) if not f.startswith('.')]
    if not files: return None
    return os.path.join(folder_path, files[0])

def upload_to_catbox(file_path):
    """Upload to Catbox"""
    try:
        url = "https://catbox.moe/user/api.php"
        payload = {'reqtype': 'fileupload'}
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': f}
            r = requests.post(url, data=payload, files=files)
        return r.text
    except: return None

def send_content(token, webhook, file_url, caption):
    """Send to specific Telegram Bot and Webhook"""
    # 1. Telegram
    if token and CHAT_ID:
        api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
        if file_url.endswith(('.mp4', '.mov', '.avi')):
            api_url = f"https://api.telegram.org/bot{token}/sendVideo"
            payload = {"chat_id": CHAT_ID, "video": file_url, "caption": caption}
        else:
            payload = {"chat_id": CHAT_ID, "photo": file_url, "caption": caption}
        try: requests.post(api_url, json=payload)
        except Exception as e: print(f"Telegram Error: {e}")
    
    # 2. Webhook
    if webhook:
        data = {"content": f"{caption}\n{file_url}"}
        try: requests.post(webhook, json=data)
        except: pass

def process_topic(topic_data):
    """Logic to process a single topic"""
    print(f"🚀 Processing Topic: {topic_data['id']}")
    
    file_path = None
    file_to_delete = None

    # Step A: Get Content
    if topic_data['type'] == 'folder':
        file_path = get_file_from_folder(topic_data['folder_path'])
        file_to_delete = file_path
    else:
        file_path = create_motivation_image()
        # Motivation is temp file, delete locally only
        
    if not file_path:
        print(f"❌ No content found for {topic_data['id']}")
        return

    # Step B: Upload
    catbox_url = upload_to_catbox(file_path)
    print(f"✅ Uploaded: {catbox_url}")

    # Step C: Send (Using specific Token & Webhook)
    send_content(topic_data['token'], topic_data['webhook'], catbox_url, topic_data['seo'])

    # Step D: Cleanup
    if topic_data['type'] == 'folder' and file_to_delete:
        os.remove(file_to_delete) # Delete from GitHub repo
        print("🗑️ File deleted from folder")
    elif topic_data['type'] == 'generated':
        os.remove(file_path) # Delete temp image

# --- MAIN EXECUTION ---
def main():
    # Load State
    if not os.path.exists('state.json'):
        with open('state.json', 'w') as f: json.dump({"current_index": 0}, f)
    with open('state.json', 'r') as f: state = json.load(f)

    # LOGIC SWITCH
    if IS_MANUAL:
        print("🔧 MANUAL MODE: Posting ALL 3 Topics...")
        for topic in CONFIG:
            process_topic(topic)
        # Manual run does NOT change rotation
    else:
        print("⏰ AUTO MODE: Posting Single Rotated Topic...")
        idx = state['current_index']
        process_topic(CONFIG[idx])
        
        # Update Rotation
        next_idx = (idx + 1) % len(CONFIG)
        state['current_index'] = next_idx
        with open('state.json', 'w') as f: json.dump(state, f)

if __name__ == "__main__":
    main()
