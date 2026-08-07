import os
import json
import random
import requests
import textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# --- CONFIGURATION ---
SUCCESS_BOT_TOKEN = os.getenv("SUCCESS_BOT_TOKEN")
SUCCESS_CHAT_ID = os.getenv("SUCCESS_CHAT_ID")

ERROR_BOT_TOKEN = os.getenv("ERROR_BOT_TOKEN")
ERROR_CHAT_ID = os.getenv("ERROR_CHAT_ID")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

SOCIAL_MEDIA_NAME = "Instagram/Facebook"
AUTOMATION_NAME = "Daily Quote Image Automator"
FIXED_AUTHOR = "Lucas Hart"

# --- MULTIPLE USER AGENTS ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/114.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/114.0.1823.43"
]

def get_headers():
    return {'User-Agent': random.choice(USER_AGENTS)}

def send_telegram(token, chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"Telegram bhejne me error: {e}")

# --- 30 DAYS COOLING LOGIC ---
def load_history():
    if not os.path.exists("history.json"):
        return {"images": {}, "titles": {}, "hashtags": {}}
    with open("history.json", "r") as f:
        try:
            return json.load(f)
        except:
            return {"images": {}, "titles": {}, "hashtags": {}}

def save_history(history):
    with open("history.json", "w") as f:
        json.dump(history, f, indent=4)

def is_cooled_down(item_name, category, history):
    last_used = history.get(category, {}).get(item_name)
    if not last_used: return True
    
    last_used_date = datetime.strptime(last_used, "%Y-%m-%d")
    if (datetime.now() - last_used_date).days >= 30:
        return True
    return False

def get_item_with_cooling(items_list, category, history):
    random.shuffle(items_list)
    for item in items_list:
        if is_cooled_down(item, category, history):
            return item
    return None

def get_file_with_cooling(folder, category, history):
    if not os.path.exists(folder): return None
    
    # 🔴 FIX FOR "1.TXT" ERROR: Filter only valid image files
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    files = [
        os.path.join(folder, f) for f in os.listdir(folder) 
        if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(valid_extensions)
    ]
    
    return get_item_with_cooling(files, category, history)

def get_text_with_cooling(filename, category, history):
    if not os.path.exists(filename): return None
    with open(filename, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return get_item_with_cooling(lines, category, history)

# --- QUOTE & IMAGE GENERATION (4:5 Ratio) ---
def get_free_quote_only():
    try:
        res = requests.get("https://zenquotes.io/api/random", headers=get_headers(), timeout=10)
        return res.json()[0]['q']
    except: return "Your only limit is your mind."

def create_image_post(quote_text, history):
    bg_path = get_file_with_cooling("images", "images", history)
    if not bg_path: 
        raise Exception("Images folder khali hai ya sabhi valid images 30 din ke cooling me hain!")

    img = Image.open(bg_path).convert("RGB")
    TARGET_W, TARGET_H = 1080, 1350

    # 1. Center Crop to 4:5 Aspect Ratio
    img_w, img_h = img.size
    target_ratio = TARGET_W / TARGET_H
    img_ratio = img_w / img_h
    
    if img_ratio > target_ratio:
        new_w = int(img_h * target_ratio)
        left = (img_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, img_h))
    else:
        new_h = int(img_w / target_ratio)
        top = (img_h - new_h) // 2
        img = img.crop((0, top, img_w, top + new_h))
        
    img = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    
    # 2. Darken background (0.6 brightness)
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(0.6)
    
    draw = ImageDraw.Draw(img)
    
    # Font setup
    try:
        font_quote = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 65)
        font_author = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
    except:
        font_quote = ImageFont.load_default()
        font_author = ImageFont.load_default()

    # 3. Add Quote (Upper-mid side)
    wrapped_quote = textwrap.fill(f"\"{quote_text}\"", width=25)
    bbox_quote = draw.multiline_textbbox((0, 0), wrapped_quote, font=font_quote, align='center')
    text_w = bbox_quote[2] - bbox_quote[0]
    text_h = bbox_quote[3] - bbox_quote[1]
    
    # Quote Position
    x_quote = (TARGET_W - text_w) / 2
    y_quote = 400 
    
    draw.multiline_text((x_quote, y_quote), wrapped_quote, font=font_quote, fill="white", align="center")
    
    # 4. Add Author Name Exactly 3 Lines Below Quote
    author_text = f"- {FIXED_AUTHOR}"
    bbox_author = draw.textbbox((0, 0), author_text, font=font_author)
    author_w = bbox_author[2] - bbox_author[0]
    
    # Calculate gap for 3 lines based on font size
    bbox_single_line = draw.textbbox((0, 0), "A", font=font_quote)
    single_line_h = bbox_single_line[3] - bbox_single_line[1]
    three_lines_gap = single_line_h * 3 
    
    x_author = (TARGET_W - author_w) / 2
    y_author = y_quote + text_h + three_lines_gap  # Quote end + 3 lines gap
    
    draw.text((x_author, y_author), author_text, font=font_author, fill="white")
    
    output_path = "final_post.jpg"
    img.save(output_path, quality=95)
    
    # Update History
    today = datetime.now().strftime("%Y-%m-%d")
    history["images"][bg_path] = today
    
    return output_path, history

# --- FAST UPLOAD LOGIC ---
def upload_media_with_fallbacks(file_path):
    filename = os.path.basename(file_path)
    print("🚀 Starting Fast 10-Server Upload for Image...")

    servers = [
        ("Catbox", lambda: requests.post("https://catbox.moe/user/api.php", data={'reqtype': 'fileupload'}, files={'fileToUpload': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("Litterbox", lambda: requests.post("https://litterbox.catbox.moe/resources/internals/api.php", data={'reqtype': 'fileupload', 'time': '72h'}, files={'fileToUpload': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("0x0.st", lambda: requests.post("https://0x0.st", files={'file': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("Transfer.sh", lambda: requests.put(f"https://transfer.sh/{filename}", data=open(file_path, 'rb'), headers=get_headers(), timeout=30)),
        ("Tmpfiles.org", lambda: requests.post("https://tmpfiles.org/api/v1/upload", files={'file': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("File.io", lambda: requests.post("https://file.io", files={'file': open(file_path, 'rb')}, headers=get_headers(), timeout=30))
    ]

    for name, req_func in servers:
        print(f"Trying {name}...")
        try:
            res = req_func()
            if res.status_code in [200, 201]:
                if name == "Tmpfiles.org":
                    return res.json()['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
                if name == "File.io":
                    return res.json()['link']
                url = res.text.strip()
                if url.startswith("http"): return url
        except Exception as e:
            print(f"{name} Failed: {e}")
            continue
            
    raise Exception("Sabhi upload servers fail ho gaye!")

# --- MAIN EXECUTION ---
def main():
    try:
        history = load_history()
        
        # 1. Fetch Title and Hashtag with Cooling
        title = get_text_with_cooling("titles.txt", "titles", history)
        hashtag = get_text_with_cooling("hashtags.txt", "hashtags", history)
        
        if not title: raise Exception("Sabhi Titles cooling me hain ya titles.txt khali hai!")
        if not hashtag: raise Exception("Sabhi Hashtags cooling me hain ya hashtags.txt khali hai!")

        # 2. Get Quote & Create Image Post
        quote = get_free_quote_only()
        image_path, history = create_image_post(quote, history)
        
        # 3. Upload Image
        media_url = upload_media_with_fallbacks(image_path)
        
        # 4. Send to Webhook (Contains Image URL, Title, Hashtag)
        webhook_data = {
            "media_url": media_url,
            "title": title,
            "hashtags": hashtag,
            "social_media": SOCIAL_MEDIA_NAME
        }
        webhook_res = requests.post(WEBHOOK_URL, json=webhook_data, timeout=20)
        
        if webhook_res.status_code not in [200, 201, 204]:
            raise Exception(f"Webhook Failed with status {webhook_res.status_code}")

        # 5. Update History & Save
        today = datetime.now().strftime("%Y-%m-%d")
        history["titles"][title] = today
        history["hashtags"][hashtag] = today
        save_history(history)
        
        # 6. Success Telegram Message
        msg = f"✅ SUCCESS!\nSocial Media: {SOCIAL_MEDIA_NAME}\nAutomation: {AUTOMATION_NAME}\nPost URL: {media_url}"
        send_telegram(SUCCESS_BOT_TOKEN, SUCCESS_CHAT_ID, msg)
        print("Done successfully!")

    except Exception as e:
        # Error Telegram Message
        error_msg = f"❌ ERROR!\nSocial Media: {SOCIAL_MEDIA_NAME}\nAutomation: {AUTOMATION_NAME}\nError Detail: {str(e)}"
        send_telegram(ERROR_BOT_TOKEN, ERROR_CHAT_ID, error_msg)
        print(f"Failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()
