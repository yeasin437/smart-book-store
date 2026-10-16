# Lumina — AI-enabled Multimodal Smart Bookstore

A runnable **Python desktop application** for the project's 10 listed requirements. The default workflow is entirely local; Ollama is needed to answer unrestricted general questions and to rephrase retrieved passages with a local LLM. Wallet funds are simulated (no payment processor).

## Run on Windows 10/11 (PowerShell)

**Easy way:** Extract this ZIP into a folder, double-click `INSTALL_WINDOWS.bat` once, then double-click `RUN_WINDOWS.bat`. The installer looks for Python 3.13, then 3.12, then 3.11. If you prefer manual setup, follow the steps below.

1. Install **Python 3.11, 3.12, or 3.13 (64-bit)** from python.org and check **Add Python to PATH**. Make sure you have a working microphone. Windows Settings → Privacy & security → Microphone → enable desktop app microphone access.
2. Extract the ZIP file to a folder, for example `C:\Users\YourName\Documents\SmartBookstore`. Open that folder, then right-click in Explorer → **Open in Terminal** (or open PowerShell and `cd` to that folder).
3. Create a separate environment and install required packages:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

   If you have Python 3.12 instead, use `py -3.12 -m venv .venv`. If PowerShell blocks activation, execute `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then try activation again. Or skip activation and call `.\.venv\Scripts\python.exe main.py`.

4. **Optional face login:** if your computer has a camera and you want face authentication in addition to voice, install:

   ```powershell
   python -m pip install -r requirements-face.txt
   ```

   This **optional** face authenticator uses OpenCV Haar face detection and an LBPH face classifier; it is **not YOLO**. The project specification also permits **a short-audio classifier as the alternative** to YOLO-based face identification. The required short-audio voice classifier is included and works without OpenCV. If you previously installed `opencv-python`, remove it first to avoid conflicts: `python -m pip uninstall -y opencv-python opencv-python-headless`, then install the face requirements.

5. Start the app:

   ```powershell
   python main.py
   ```

6. The first launch automatically opens **Create & Enroll** for the super-user. Choose a username and password (no built-in default admin password). Select **Voice**; when you click Create & Enroll, speak the exact phrase **“My voice opens this smart bookstore”** 3 times (3 seconds per sample with a short break). You can select **Face** instead after installing the optional package; a camera window opens, and you press **SPACE** eight times when exactly one face is visible (ESC cancels).
7. Sign out, then create a registered customer with another username/password and enroll voice or face. **Sign in always checks both your password and the matching voice or face template**. As a visitor, you can browse, search, chat and review without logging in.

### To enable the free local LLM (Ollama)

Install [Ollama](https://ollama.com/download), start it, and in another PowerShell terminal run:

```powershell
ollama pull llama3.2:1b
```

The program calls the local model at `http://127.0.0.1:11434/api/chat`. The default model is `llama3.2:1b`. Optionally change it before launching:

```powershell
$env:OLLAMA_MODEL='llama3.2:1b'
python main.py
```

**RAG still works without Ollama**: it finds authorized passages in local files and labels responses `[RAG ...]`, using an extract instead of LLM-generated phrasing. General questions will explicitly say `[LLM UNAVAILABLE]` until Ollama and its model are installed. No paid API keys are needed.

## How to try the main features

- **Home**: the first 3 recommendations for anonymous/administrator users come from globally browsed and purchased books; registered/VIP users additionally use their own browsing/purchase history.
- **Book catalog**: search by title, keyword, author, year or category. Select a book to record a browsing event; click **Search image…** and choose one of the images in `sample_images/` to test cover matching, or attach your own covers/internal figures to new books.
- **Book purchase**: sign in as RC/VC; open **My wallet**, top up demo dollars (e.g. `100.00`), then select a book and buy. Wallet overdraft is permitted with a **$1 fine**; accounts with negative balances become suspended instantly, including no further biometric login. The super-user deposits sufficient money and uses **Deposit / reopen selected account** to reactivate.
- **VIP**: RC becomes VC automatically after **more than 3 purchases OR over $200 of cumulative purchase spending**. VC receives **10% off subsequent purchases**.
- **Reviews**: any visitor or active account can submit 1–5 stars + comment. Purchased reviewers get double weight, and blocked reviews don't affect order lists. Four or more eligible reviews with average less than 2 trigger **no-order**, while average greater than 4 triggers **to-order**. Taboo words are masked with asterisks; **more than 3 occurrences** block the comment and add a warning to logged-in reviewers. On a blocked comment, a VC is demoted to RC; an RC with more than 2 total warnings is suspended. SU and visitor nicknames also accumulate warnings.
- **Assistant**: queries are routed to **role-filtered local RAG first**, then to the local Ollama model. Public, registered, VIP, and admin knowledge documents are stored in `knowledge/`; the chat labels answers `[RAG ...]`, `[LLM ...]`, or `[SYSTEM FINANCE ...]`. Finance is answered deterministically from the database **for super-user only**, not by an LLM.
- **Reading journey**: creative feature combining your browsing history and a topic to generate a 3-book, explainable reading path. (Rule-based, not a trained recommender.)
- **Super-user**: add titles and pictures, adjust price and stock, change forbidden-word list, reopen accounts, inspect finance totals and order lists.

## Run automated tests

```powershell
python -m unittest discover -s tests -v
```

Tests verify purchases/fines, suspension/reopening, VIP promotions, review weights/moderation, admin permissions, RAG retrieval, image hashes, and audio feature extraction. To run a microphone and camera smoke test, use the interactive login/enrollment screens; automated tests cannot meaningfully test physical hardware.

## Project structure

```text
SmartBookstore/
├── main.py                  # Launch GUI
├── INSTALL_WINDOWS.bat      # One-time Windows dependency setup
├── RUN_WINDOWS.bat          # One-click Windows launch
├── smartbookstore/
│   ├── database.py          # SQLite persistence and business rules
│   ├── gui.py               # Tkinter desktop windows
│   ├── biometrics.py        # Voice MFCC features, optional OpenCV face matching
│   ├── intelligence.py      # Role-scoped local retrieval and Ollama
│   └── image_search.py      # Cover / figure perceptual hash search
├── knowledge/
│   ├── public/              # Public store and team RAG facts
│   ├── registered/          # RC+ only knowledge
│   ├── vip/                 # VC+ only knowledge
│   └── admin/               # SU only knowledge
├── sample_images/           # Example covers for generated starter catalog
├── tests/                   # Automated unit tests
├── requirements.txt
└── requirements-face.txt
```

Data is created at `data/bookstore.sqlite3`. Book images, face samples and voice features are stored under `data/` locally. **Never publish your local `data/` directory** (it contains user information and biometric templates). You can delete `data/` to reset a local demo; all accounts, wallet balances, reviews, and purchases will be lost.

## Important limits and implementation notes

- **Academic/demo prototype, not production commerce or security.** Voice MFCC nearest-template classification and LBPH face matching are limited biometric demos with no liveness/spoof detection. An attacker may impersonate a voice using recordings. Password + biometric verification is used, but cannot be treated as strong identity assurance. The app does not connect to payment networks, charge credit cards, or send real money.
- This application chooses **SQLite local storage**, even though the spec allows plain files. No separate database server is required.
- The voice classifier is deliberately small/offline; its accuracy depends on the microphone and environment. If enrollment or login fails, use consistent distance/volume and say the full phrase clearly. You can choose the optional face route instead. No bypass login is provided.
- Local file RAG uses lexical TF-IDF-style retrieval, not a paid embedding model. Public/VIP/admin knowledge is separated to prevent accidental cross-role document retrieval. Retrieved text can contain unwanted content; only include trusted files in `knowledge/`.
- The built-in books are fictional **store listings for public-domain titles** (prices and stocks are demonstration values); no copyrighted book text is included. Covers are generated placeholder graphics; attach your own lawful cover and internal figure images to newly added books.
- This demo includes one initial super-user. Additional super-users cannot self-register. Book inventory editing is via the admin tab.

## Requirement traceability (from project specification)

| # | Requirement | Implementation |
|---|---|---|
| 1 | SU, VS, RC, VC roles | Role-based tabs and authorization, `database.py` |
| 2 | Top three book recommendations | `recommendations()` and Home cards |
| 3 | Chat with increasing role privileges | Local RAG/LLM limits plus SU-only finance |
| 4 | Face and/or voice biometric login | Password + MFCC voice classifier, optional face LBPH |
| 5 | SU book creation, browse/search text and image | Catalog, admin form, image perceptual hash |
| 6 | Wallet, $1 overdraft fine, suspensions | Atomic `purchase()`, `deposit()` |
| 7 | Ratings, weighted reviews, order lists and moderation | `review()`, `book_rating()`, `order_lists()` |
| 8 | VIP >3 buys OR >$200, 10% discount | `purchase()` promotion, discounts |
| 9 | Local RAG first, otherwise LLM; explicitly label | `retrieve()` + `ask()` |
| 10 | Creative AI feature | Personalized 3-book reading journey |

