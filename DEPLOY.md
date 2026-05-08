# 🚀 Deploying to Streamlit Cloud — Step-by-Step

## What you'll need
- A free **GitHub** account → https://github.com
- A free **Streamlit Cloud** account → https://share.streamlit.io

---

## Your repo must contain exactly these files

```
your-repo/
├── browser_app.py          ← the Streamlit app
├── requirements.txt        ← Python packages
├── packages.txt            ← Linux system libraries for Chromium
└── .streamlit/
    └── config.toml         ← dark theme + server settings
```

> ⚠️ All four items are critical. Missing `packages.txt` will cause Chromium to fail silently.

---

## Step 1 — Create a new GitHub repository

1. Go to https://github.com/new
2. Fill in:
   - **Repository name**: `isolated-browser` (or anything you like)
   - **Visibility**: Public ✅  *(Streamlit Cloud free tier requires public repos)*
   - Leave "Add README" **unchecked** (you'll push your own files)
3. Click **Create repository**
4. GitHub will show you an empty repo page — keep this tab open.

---

## Step 2 — Upload your files to GitHub

### Option A — GitHub web UI (no Git knowledge needed)

1. On your empty repo page, click **"uploading an existing file"** (or the **Add file → Upload files** button).

2. Drag-and-drop (or select) these four items:
   ```
   browser_app.py
   requirements.txt
   packages.txt
   ```
3. Click **Commit changes**.

4. Now create the `.streamlit/` folder:
   - Click **Add file → Create new file**
   - In the filename box type exactly: `.streamlit/config.toml`
     *(typing the slash creates the folder automatically)*
   - Paste the contents of `config.toml` into the editor
   - Click **Commit new file**

### Option B — Git command line

```bash
# Clone the empty repo GitHub just gave you
git clone https://github.com/YOUR_USERNAME/isolated-browser.git
cd isolated-browser

# Copy all four files into this folder
cp /path/to/browser_app.py .
cp /path/to/requirements.txt .
cp /path/to/packages.txt .
mkdir -p .streamlit
cp /path/to/config.toml .streamlit/

# Push
git add .
git commit -m "Initial deploy"
git push origin main
```

---

## Step 3 — Connect Streamlit Cloud to your repo

1. Go to https://share.streamlit.io and sign in (you can use your GitHub account).

2. Click the **"New app"** button (top-right).

3. Fill in the form:

   | Field | Value |
   |---|---|
   | **Repository** | `YOUR_USERNAME/isolated-browser` |
   | **Branch** | `main` |
   | **Main file path** | `browser_app.py` |
   | **App URL** *(optional)* | Pick a custom slug, e.g. `my-browser` |

4. Click **Deploy!**

---

## Step 4 — Wait for the first build (~3–5 minutes)

Streamlit Cloud will:

```
[1/4]  Install Linux packages from packages.txt    ← apt-get install
[2/4]  Install Python packages from requirements.txt ← pip install playwright
[3/4]  Start the Streamlit server
[4/4]  On first page load: playwright install chromium  ← ~130 MB download
```

You'll see a "Your app is in the oven" screen with build logs.
Click **"Manage app"** (bottom-right of the logs) to watch in real time.

> 🕐 The **first cold start** (step 4/4 above) takes ~60–90 seconds because
> Playwright downloads the Chromium binary. Subsequent loads are instant
> because `@st.cache_resource` caches it for the server's lifetime.

---

## Step 5 — Open your app

Once the build is green, Streamlit Cloud gives you a public URL:

```
https://YOUR_USERNAME-isolated-browser-browser-app-XXXX.streamlit.app
```

Visit it and the browser will load Google on first render.

---

## Troubleshooting

### "playwright._impl._errors.Error: Executable doesn't exist"
→ The `_ensure_chromium()` function failed.
Check the app logs (☰ → Manage app → Logs) for a timeout or network error.
Try restarting the app once from the Streamlit dashboard.

### Page loads but screenshot is blank / grey
→ The page likely relies on heavy JavaScript.
Increase `time.sleep(0.35)` to `time.sleep(1.0)` in `act_navigate()`.

### "libXXX.so not found" or similar Chromium crash
→ A system library is missing from `packages.txt`.
Add the missing library name to `packages.txt`, commit, and Streamlit Cloud
will rebuild automatically.

### App is very slow on Streamlit Cloud
→ The free tier has limited RAM (~1 GB) and CPU.
Chromium itself uses ~200–300 MB.  For a faster experience, upgrade to
Streamlit Cloud's paid tier, or self-host on a VPS (e.g. Fly.io, Railway, Render).

### "This app has gone to sleep" (cold start)
→ Streamlit Cloud free tier hibernates apps after ~7 days of inactivity.
First load after hibernation re-downloads the Chromium binary (~90 s).
This is normal.

---

## Re-deploying after code changes

Just push a commit to your GitHub repo — Streamlit Cloud auto-redeploys:

```bash
# After editing browser_app.py locally:
git add browser_app.py
git commit -m "Update app"
git push origin main
# Streamlit Cloud picks up the change and redeploys within ~1 minute
```

---

## File contents reference

### `requirements.txt`
```
streamlit>=1.32.0
playwright>=1.43.0
```

### `packages.txt`  (Linux system libraries for Chromium)
```
libnss3
libnspr4
libatk1.0-0
libatk-bridge2.0-0
libcups2
libdrm2
libdbus-1-3
libxkbcommon0
libxcomposite1
libxdamage1
libxfixes3
libxrandr2
libgbm1
libasound2
libpangocairo-1.0-0
libpango-1.0-0
libcairo2
libatspi2.0-0
libwayland-client0
```

### `.streamlit/config.toml`
```toml
[theme]
base = "dark"
backgroundColor          = "#0d1117"
secondaryBackgroundColor = "#161b22"
textColor                = "#c9d1d9"
primaryColor             = "#58a6ff"

[server]
headless = true
enableCORS = false
enableXsrfProtection = false
```
