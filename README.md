# 氣絕錄 · Khí Tuyệt Lục — bot Discord báo tử

Bot nhận sự kiện chết từ **PBZ Death Tracker** (thư mục `..\`), rồi đăng vào một
hoặc nhiều kênh Discord: **ảnh nằm trên, embed kiếm hiệp / nhập ma nằm dưới**.

- Chạy 24/7 trên **Render.com (free)** dạng Web Service, giữ thức bằng **UptimeRobot**.
- Cấu hình bằng lệnh `/ktl` trong Discord, **sống sót qua mọi lần deploy**
  (vì được lưu trong một message ghim của chính Discord, không phải đĩa của Render).
- Nhiều kênh, mỗi kênh bật/tắt ảnh riêng.

---

## 1. Cần chuẩn bị

| Thứ | Ghi chú |
|---|---|
| Tài khoản Discord + server riêng | bạn phải có quyền **Quản lý máy chủ** |
| Discord Developer Portal | mở sẵn tab **Bot** |
| Tài khoản GitHub | Render deploy từ repo GitHub |
| Tài khoản Render | gói Free |
| Tài khoản UptimeRobot | gói Free, monitor 5 phút |

---

## 2. Tạo bot trên Discord Developer Portal

1. https://discord.com/developers/applications → **New Application** → tên `Khí Tuyệt Lục` → Create.
2. Tab **Bot** → **Reset Token** → **Copy** → dán vào ô `DISCORD_TOKEN` (chỉ hiện 1 lần,
   mất thì reset lại). **Không gửi token cho ai, không commit lên GitHub.**
3. Tab **Bot** → mục *Privileged Gateway Intents*: **không cần bật gì** (bot dùng slash command).
4. Tab **OAuth2 → General** → copy **Application ID** (cần cho link mời).
5. Mời bot vào server bằng link sau (thay `APP_ID`):

```
https://discord.com/oauth2/authorize?client_id=APP_ID&permissions=117776&scope=bot%20applications.commands
```

`permissions=117776` = Xem kênh, Gửi tin nhắn, Nhúng liên kết, Đính kèm tệp,
Đọc lịch sử tin nhắn, Quản lý kênh (để bot tự tạo kênh cấu hình).

6. Lấy **ID server**: Discord → Settings → Advanced → bật **Developer Mode** →
   chuột phải lên tên server → **Copy Server ID** → đó là `GUILD_ID`.
   (Có ID này thì slash command hiện ngay; không có thì phải chờ tới 1 giờ.)

---

## 3. Chạy thử trên máy (nên làm, 2 phút)

```bat
cd "D:\Game\Phantom Blade Zero\bot code\bot"
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env        :: điền DISCORD_TOKEN, API_TOKEN, GUILD_ID rồi lưu
run_local.bat
```

Thấy log `đã đăng nhập: Khí Tuyệt Lục#xxxx` là được. Ctrl+C để dừng.
`API_TOKEN` là chuỗi bí mật **bạn tự nghĩ ra** (ví dụ `pbz-2026-huyet-thu`), nó chỉ
cần trùng với `token` trong `config.toml` của tracker.

Kiểm thử offline (không cần token, không cần mạng):

```bat
python tools\test_embed.py
python tools\test_notify.py
python tools\test_webhook.py
cd .. && python tools\test_contract.py
```

---

## 4. Đưa lên Render

### 4.1 Đẩy code lên GitHub

Chỉ đẩy **thư mục bot**, không đẩy cả `bot code` (trong đó có file game rất nặng):

```bat
cd "D:\Game\Phantom Blade Zero\bot code\bot"
git add .
git commit -m "Khi Tuyet Luc discord bot"
git push
```

Repo hiện tại: `https://github.com/dtake04092006-pixel/MingJin` (nhánh `main`).
Nếu dựng lại từ đầu: `git init` → các lệnh trên → `git remote add origin <link-repo>`
→ `git push -u origin main`.

(`.gitignore` đã chặn `.env`, `data/`, `__pycache__`.)

### 4.2 Tạo Web Service

**Cách A — dùng file `render.yaml` (nhanh):** Render → **New +** → **Blueprint** →
chọn repo → Apply. Sau đó vào service → Environment → điền 3 bí mật.

> Nếu bạn push **cả** thư mục `bot code` (bot nằm trong `bot code/bot`), mở `render.yaml`
> và bỏ dấu `#` ở dòng `rootDir: bot code/bot` trước khi Apply.

**Cách B — thủ công (chắc ăn nhất):**

| Trường | Giá trị |
|---|---|
| Type | **Web Service** |
| Region | **Singapore** (gần VN nhất) |
| Branch | `main` |
| Root Directory | để trống (nếu repo chỉ chứa bot) |
| Runtime | **Python 3** |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m khi_tuyet_luc` |
| Instance Type | **Free** |
| Health Check Path | `/health` |

> Start Command **phải** đúng `python -m khi_tuyet_luc`. Nếu service được tạo từ
> trước đợt đổi tên và vẫn ghi `python -m menh_tan`, bot vẫn chạy được nhờ cầu
> nối `menh_tan/__main__.py`, nhưng nên sửa lại lệnh cho gọn: Settings →
> Build & Deploy → Start Command → **Save Changes** → Manual Deploy.

### 4.3 Biến môi trường (tab Environment)

| Key | Value |
|---|---|
| `DISCORD_TOKEN` | token ở bước 2 |
| `API_TOKEN` | chuỗi bí mật bạn tự nghĩ (phải trùng tracker) |
| `GUILD_ID` | ID server ở bước 2 |
| `PYTHON_VERSION` | `3.12.10` |
| `IMAGE_MODE` | `on` |

Bấm **Save Changes** → Render tự deploy. Chờ log:

```
INFO  khi_tuyet_luc.web: HTTP nghe trên 0.0.0.0:10000
INFO  khi_tuyet_luc.bot: đăng ký 12 slash command vào guild ...
INFO  khi_tuyet_luc.bot: đã đăng nhập: Khí Tuyệt Lục#xxxx (guild: 1)
WARNING khi_tuyet_luc.bot: chưa cấu hình kênh nào — chạy /ktl add trong server
```

Mở `https://<tên-app>.onrender.com/` → thấy trang **氣絕錄 · Khí Tuyệt Lục** là web đã sống.

> Gói Free **ngủ sau 15 phút** không có truy cập; lần gọi đầu sau khi ngủ mất ~30–60 giây.
> Bước 5 giải quyết việc này.

---

## 5. UptimeRobot giữ bot thức

1. https://uptimerobot.com → **Add New Monitor**.
2. Type **HTTP(s)**, Friendly name `Khí Tuyệt Lục`, URL:
   `https://<tên-app>.onrender.com/health`
3. Monitoring Interval **5 minutes** → Create.
4. (Tuỳ chọn) bật cảnh báo email khi bot chết.

UptimeRobot ping mỗi 5 phút → Render không ngủ → tracker gửi phát nào ăn phát đó.
Gói Render free có 750 giờ/tháng, một service chạy 24/7 chỉ tốn ~744 giờ → vừa đủ.

---

## 6. Cấu hình trong Discord

Gõ trong server (cần quyền Quản lý máy chủ):

```
/ktl setup                 ← tạo #khi-tuyet-luc-config, ghim cấu hình (LÀM ĐẦU TIÊN)
/ktl add channel:#huyết-thư
/ktl add channel:#nhật-ký image:false
/ktl deaths count:39        ← đặt tổng kiếp đã có trước khi dùng tool
/ktl player member:@tên     ← tên + avatar hiện trong embed (bỏ trống = xoá)
/ktl test                  ← xem thử embed + ảnh
/ktl list
/ktl image channel:#nhật-ký mode:on
/ktl default-image mode:off
/ktl status
/ktl remove channel:#nhật-ký
/ktl pause                 ← tạm ngưng (tracker vẫn gửi được, bot bỏ qua)
/ktl resume
```

`/ktl setup` rất quan trọng: nó tạo message ghim giữ cấu hình. Đừng xoá kênh
`#khi-tuyet-luc-config` hay message ghim trong đó — mất là mất cấu hình (phải `setup` lại).

---

## 7. Nối tracker với bot

Mở `..\config.toml` của tracker:

```toml
[bot]
endpoint = "https://<tên-app>.onrender.com/api/deaths"   # KHÔNG phải 127.0.0.1
token    = "chuỗi-bí-mật-trùng-API_TOKEN"
timeout_s  = 10      # Render free ngủ thì lần đầu phải chờ khởi động
send_image = true    # false = chỉ gửi embed, không upload ảnh
```

Rồi chạy tracker (`..\run.bat`). Mỗi lần chết: tracker ghi SQLite + ảnh, đẩy event
lên bot; bot đăng vào các kênh đã cấu hình.

Gõ sai token → log tracker hiện `HTTP 403 (token sai? ...)` và event **vẫn nằm trong
outbox** để gửi lại sau.

---

## 8. Kiểm thử offline

| Lệnh | Nội dung |
|---|---|
| `python tools\test_embed.py` | 53 kiểm tra: embed, giới hạn Discord, kho chữ, lưu cấu hình |
| `python tools\test_notify.py` | 32 kiểm tra: nhiều kênh, bật/tắt ảnh, chống trùng, liên tử, lỗi quyền |
| `python tools\test_webhook.py` | 33 kiểm tra: token, JSON hỏng, base64, 503/400/403 |
| `python ..\tools\test_contract.py` | 14 kiểm tra: tracker gửi thật → handler thật, ảnh base64 giống hệt file gốc |

---

## 9. Cấu trúc code

```
khi_tuyet_luc/
  __main__.py   entrypoint: HTTP server + bot Discord + SIGTERM
  settings.py   đọc env / .env, kiểm tra bắt buộc
  texts.py      câu thơ, Hán tự, bậc "chuyển", tầng ma khí
  event.py      parse payload tracker, giải mã ảnh base64 (≤ 8 MB, JPEG/PNG)
  embed.py      dựng embed + tự kiểm tra giới hạn Discord
  store.py      cấu hình: cache + message ghim Discord + env
  notify.py     gửi tới nhiều kênh, chế độ ảnh, chống trùng id, tính liên tử
  web.py        aiohttp: /health, /, /api/deaths
  commands.py   12 lệnh slash
  bot.py        lớp Bot, đồng bộ slash command, flush cấu hình định kỳ
tools/
  _common.py, test_embed.py, test_notify.py, test_webhook.py
```

---

## 10. Sự cố thường gặp

| Hiện tượng | Nguyên nhân / cách sửa |
|---|---|
| Không thấy `/ktl` | thiếu `GUILD_ID`, hoặc invite thiếu scope `applications.commands`; sửa env rồi **Manual Deploy** lại |
| Log `Improper token` | token sai/hết hiệu lực → Reset Token trong portal, cập nhật env Render |
| Tracker báo `HTTP 403` | `token` trong config.toml ≠ `API_TOKEN` trên Render |
| Tracker báo `HTTP 503` | bot chưa có kênh → `/ktl add` |
| Tracker báo timeout lần đầu | Render đang ngủ → chờ 60 giây, event sẽ được gửi lại; bật UptimeRobot |
| Ảnh không hiện, chỉ có embed | kênh đó đang `image:false`, hoặc event không có ảnh (footer ghi *vô ảnh*), hoặc bot thiếu quyền **Đính kèm tệp** |
| Mất cấu hình sau khi deploy | chưa chạy `/ktl setup` (không có message ghim để đọc lại) |
| Bot im sau khi Render restart | `#khi-tuyet-luc-config` bị xoá hoặc mất quyền Đọc lịch sử tin nhắn → cấp lại quyền, chạy lại `setup` |
| Build fail trên Render | kiểm tra `PYTHON_VERSION=3.12.10` và file `requirements.txt` |

---

## 11. Bảo mật

- Token và `API_TOKEN` chỉ nằm trong **Environment của Render** và `.env` ở máy
  (đã bị `.gitignore` chặn). Repo công khai cũng không lộ.
- `/api/deaths` so token bằng `hmac.compare_digest`; thiếu/sai → 403, không lộ chi tiết.
- Trang `/` chỉ hiện số kênh, uptime, số event — không hiện token, không hiện ID kênh.
- Nếu nghi token lộ: Reset Token ở portal → cập nhật env Render → (tuỳ chọn) đổi `API_TOKEN`.

---

## 12. Ghi chú thiết kế

- **Ảnh trên, embed dưới:** ảnh gửi dạng attachment thường (`discord.File`), **không**
  dùng `embed.set_image` (cách đó nhét ảnh vào đáy embed). Discord luôn vẽ attachment
  phía trên embed trong cùng một message.
- **Vì sao gửi ảnh dạng base64:** bot chạy trên cloud nên không đọc được đường dẫn file
  trên máy bạn. Tracker mã hoá ảnh (~150 KB → ~200 KB) đúng lúc gửi; file trong
  `outbox/` vẫn không chứa base64 nên đĩa không phình.
- **Vì sao cấu hình nằm trong Discord:** đĩa của Render Free là ephemeral, mất khi
  deploy/restart. Message ghim là "database" miễn phí, bền vĩnh viễn.
- **Vì sao 503 khi chưa có kênh:** thà giữ event trong outbox (tracker tự retry, tối đa
  5 phút/lần) còn hơn âm thầm mất một lần chết.
- **Chống trùng:** tracker có thể gửi lại nếu mất phản hồi; bot nhớ 500 `id` gần nhất
  nên không đăng 2 lần.
