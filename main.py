import os
import json
import requests
import textwrap
import shutil
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION & SECRETS ---
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
PIXABAY_KEY = os.getenv('PIXABAY_KEY')

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

# --- HELPER FUNCTIONS ---

def get_file_from_folder(folder_path):
    """Folder se pehli file uthata hai"""
    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return None
    
    # Hidden files (jaise .gitkeep) ko ignore karein
    files = [f for f in sorted(os.listdir(folder_path)) if not f.startswith('.')]
    
    if not files:
        print(f"Folder is empty: {folder_path}")
        return None

    # Pehli file select karein
    file_name = files[0]
    full_path = os.path.join(folder_path, file_name)
    return full_path

def create_motivation_image():
    """Motivational Image create karta hai"""
    q_res = requests.get("https://zenquotes.io/api/random")
    quote_data = q_res.json()[0]
    quote_text = f'"{quote_data["q"]}"'
    author_text = "- Lucas Hart"

    pix_url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q=nature+dark&image_type=photo&orientation=vertical"
    bg_data = requests.get(pix_url).json()
    bg_url = bg_data['hits'][0]['largeImageURL']
    
    img_data = requests.get(bg_url).content
    with open("temp_bg.jpg", "wb") as f: f.write(img_data)

    img = Image.open("temp_bg.jpg").convert("RGB")
    img = img.resize((1080, 1350))
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 120))
    img.paste(overlay, (0, 0), overlay)
    draw = ImageDraw.Draw(img)

    font_url = "https://github.com/google/fonts/raw/main/apache/robotoslab/RobotoSlab-Bold.ttf"
    with open("font.ttf", "wb") as f: f.write(requests.get(font_url).content)
    
    font_quote = ImageFont.truetype("font.ttf", 55)
    font_author = ImageFont.truetype("font.ttf", 40)

    lines = textwrap.wrap(quote_text, width=25)
    y_text = 500
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        w = bbox[2] - bbox[0]
        draw.text(((1080 - w) / 2, y_text), line, font=font_quote, fill="white")
        y_text += 70
    
    y_text += 40
    bbox = draw.textbbox((0, 0), author_text, font=font_author)
    w = bbox[2] - bbox[0]
    draw.text(((1080 - w) / 2, y_text), author_text, font=font_author, fill="#FFD700")

    path = "final_motivation.jpg"
    img.save(path)
    return path

def upload_to_catbox(file_path):
    """Catbox par upload karke direct URL leta hai"""
    url = "https://catbox.moe/user/api.php"
    payload = {'reqtype': 'fileupload'}
    with open(file_path, 'rb') as f:
        files = {'fileToUpload': f}
        response = requests.post(url, data=payload, files=files)
    return response.text

def send_telegram(token, file_url, caption):
    if not token: return
    api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
    # Video support check (simple extension check)
    if file_url.endswith(('.mp4', '.mov', '.avi')):
        api_url = f"https://api.telegram.org/bot{token}/sendVideo"
        payload = {"chat_id": CHAT_ID, "video": file_url, "caption": caption}
    else:
        payload = {"chat_id": CHAT_ID, "photo": file_url, "caption": caption}
    
    try: requests.post(api_url, json=payload)
    except Exception as e: print(f"Telegram Error: {e}")

def send_webhook(webhook_url, file_url, caption):
    if not webhook_url: return
    data = {"content": f"{caption}\n{file_url}"}
    try: requests.post(webhook_url, json=data)
    except: pass

# --- MAIN LOGIC ---
def main():
    # 1. Load State
    if not os.path.exists('state.json'):
        with open('state.json', 'w') as f: json.dump({"current_index": 0}, f)
        
    with open('state.json', 'r') as f: state = json.load(f)
    idx = state['current_index']
    
    current_topic = CONFIG[idx]
    print(f"Processing Topic: {current_topic['id']}")

    file_path_to_upload = None
    file_to_delete = None # Track kaunsi file delete karni hai

    # 2. Prepare Content
    if current_topic['type'] == 'folder':
        # Folder se image uthao
        file_path_to_upload = get_file_from_folder(current_topic['folder_path'])
        file_to_delete = file_path_to_upload # Ye file repo se delete hogi
        
        if not file_path_to_upload:
            print(f"No files left in {current_topic['folder_path']}!")
            # Agar file nahi mili, to skip karke state badha do taki automation na ruke
            next_idx = (idx + 1) % len(CONFIG)
            state['current_index'] = next_idx
            with open('state.json', 'w') as f: json.dump(state, f)
            return

    else:
        # Motivation Image Generate karo
        file_path_to_upload = create_motivation_image()
        file_to_delete = None # Generated file ko repo se delete nahi karna (wo temp hai)

    # 3. Upload & Send
    if file_path_to_upload:
        catbox_link = upload_to_catbox(file_path_to_upload)
        print(f"Uploaded: {catbox_link}")

        send_telegram(current_topic['token'], catbox_link, current_topic['seo'])
        send_webhook(current_topic['webhook'], catbox_link, current_topic['seo'])

        # 4. Cleanup (Most Important Step)
        if file_to_delete:
            # Agar folder wali image thi, to usse delete karo
            print(f"Deleting used file: {file_to_delete}")
            os.remove(file_to_delete)
        
        # Agar motivation wali temp image thi, to usse bhi hata do
        if current_topic['type'] == 'generated' and os.path.exists(file_path_to_upload):
            os.remove(file_path_to_upload)

    # 5. Rotate State
    next_idx = (idx + 1) % len(CONFIG)
    state['current_index'] = next_idx
    with open('state.json', 'w') as f: json.dump(state, f)

if __name__ == "__main__":
    main()
