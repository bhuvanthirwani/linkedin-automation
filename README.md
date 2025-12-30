<div align="center">

# 🚀 LinkedIn Automation Tool   
### Smart, Stealthy, and Scalable Network Growth

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Automation-orange?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Educational-yellow?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

</div>

---

> [!WARNING]
> **Educational Purpose Only**  
> This tool is for **educational and technical evaluation purposes only**. Automating LinkedIn violates their Terms of Service and may result in account bans. Use responsibly and at your own risk.

## 🌟 Overview
This project is a powerful, educational Python-based automation tool designed to demonstrate how to programmatically interact with LinkedIn. It simulates human behavior to perform tasks like searching for professionals, sending connection requests, and managing follow-up messages.

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| 🛡️ **Anti-Detection** | Human-like mouse movements, random delays, and typing simulation to fly under the radar. |
| 🔍 **Smart Search** | Advanced filtering by **Job Title**, **Company**, **Location**, and **Keywords**. |
| 🗄️ **Database Integration** | Seamlessly fetch targets from a PostgreSQL database for scalable campaigns. |
| 🤝 **Auto-Connect** | Send personalized connection requests with daily limit enforcement. |
| 💬 **Follow-Up System** | Automated follow-up sequences for new connections using customizable templates. |
| 🔐 **Secure Auth** | Robust session management with cookie persistence and checkpoint handling. |

---

## 🛠️ Installation

### 1. Prerequisities
Ensure you have **Python 3.10+** installed.

### 2. Setup
```bash
# Clone the repository (if applicable)
# git clone ...

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

---

## ⚙️ Configuration

### 1. Environment Variables
Create a `.env` file or set these variables in your shell:

| Variable | Description |
| :--- | :--- |
| `LINKEDIN_EMAIL` | Your LinkedIn login email. |
| `LINKEDIN_PASSWORD` | Your LinkedIn login password. |
| `DB_POSTGRESDB_HOST` | (Optional) Database host. |
| `DB_POSTGRESDB_USER` | (Optional) Database user. |
| `DB_POSTGRESDB_PASSWORD` | (Optional) Database password. |

### 2. Config File
Copy the example config and customize it:
```bash
cp configs/config.example.yaml configs/config.yaml
```

<details>
<summary><strong>📝 Click to view `config.yaml` structure</strong></summary>

```yaml
linkedin:
  email: ...
  password: ...

browser:
  headless: false  # Set to true for background execution

rate_limits:
  daily_connection_limit: 25
  daily_message_limit: 50
  min_delay_seconds: 5
  max_delay_seconds: 15
```
</details>

---

## 🚀 Usage Guide

Run the bot with `python run.py`. Below are the common modes of operation.

### 🔍 Scrapping Mode
*Scrapes profiles from search results and saves them to the database.*
```bash
python run.py --mode Scrapping \
    --keywords "Senior Software Engineer" \
    --location "90000084" \
    --start-page 1 \
    --pages 5 \
    --max-connections 50
```

### 🎯 Filtering & Sending
*Checks scraped profiles for activity and sends requests.*
```bash
python run.py --mode Filtering --max-connections 20
```

### 📦 Database Mode
*Fetch specific targets from your database and connect.*
```bash
python run.py --mode database --max-connections 15
```

### 🤖 Search & Connect (Direct)
*Search and connect immediately (bypassing database).*
```bash
python run.py --mode search \
    --keywords "Founder" \
    --location "90000084" \
    --max-connections 10
```

### 📨 Follow-Up Messages
*Send follow-up messages to people who accepted your request.*
```bash
python run.py --mode followup --max-messages 10
```

### 🧪 Dry Run
*Test your command without performing actual actions.*
```bash
python run.py --mode <ANY_MODE> --dry-run
```

---

## 📂 Project Structure

```bash
linkedin-automation/
├── 📁 configs/          # Configuration files
├── 📁 data/             # Persistent data (cookies, tracking logs)
├── 📁 src/              # Source code
│   ├── 📁 auth/         # Login & Session management
│   ├── 📁 browser/      # Playwright wrapper & Anti-detect
│   ├── 📁 connection/   # Connection logic & Note composition
│   ├── 📁 database/     # DB operations
│   ├── 📁 features/     # High-level workflows (Scrapers, Filters)
│   ├── 📁 messaging/    # Message templates & Sending logic
│   └── 📁 search/       # Search execution & Parsing
├── 📄 run.py            # CLI Entry point
└── 📄 requirements.txt  # Dependencies
```

---

<div align="center">

**[🐛 Report Bug](https://github.com/yourusername/linkedin-automation/issues) | [📝 Request Feature](https://github.com/yourusername/linkedin-automation/issues)**

*Built with ❤️ for automation enthusiasts.*

</div>
