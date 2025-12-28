# LinkedIn Automation Tool
# Educational Purpose Only - Do Not Use in Production

## ⚠️ Disclaimer
This tool is for **educational and technical evaluation purposes only**.
Automating LinkedIn violates their Terms of Service and may result in account bans.

## Features
- 🔐 **Authentication**: Login with credentials, session persistence, checkpoint detection
- 🔍 **User Search**: Search by job title, company, location, keywords with pagination
- 🗄️ **Database Integration**: Fetch LinkedIn URLs from PostgreSQL database and send connection requests
- 🤝 **Connection Management**: Send personalized connection requests with daily limits
- 💬 **Follow-up Messaging**: Automated follow-up messages with template support
- 🛡️ **Anti-Detection**: Human-like behavior patterns, fingerprint masking
- 🎭 **Stealth Mode**: Random delays, natural mouse movements, typing simulation

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Configuration

1. Copy the example config:
```bash
cp configs/config.example.yaml configs/config.yaml
```

2. Set your credentials via environment variables:
```bash
set LINKEDIN_EMAIL=your_email@example.com
set LINKEDIN_PASSWORD=your_password
```

Or edit `configs/config.yaml` directly.

3. (Optional) For database mode, set database credentials:
```bash
set DB_POSTGRESDB_HOST=your_host
set DB_POSTGRESDB_PORT=5432
set DB_POSTGRESDB_DATABASE=your_database
set DB_POSTGRESDB_USER=your_user
set DB_POSTGRESDB_PASSWORD=your_password
set DB_POSTGRESDB_SCHEMA=public
```

Or configure in `configs/config.yaml` under the `database` section.

## Usage

```bash
# Run the bot
python -m src.main --config configs/config.yaml

# Search and connect mode
python -m src.main --mode search --keywords "Software Engineer" --location "San Francisco"

# Follow-up messaging mode
python -m src.main --mode followup

# Database mode - fetch URLs from database and send connection requests
python -m src.main --mode database --max-connections 10

# Database mode with custom table and WHERE clause
python -m src.main --mode database --table linkedin_db_candidate_queue --where "status = 'pending'"

# Database mode - fetch from raw_linkedin_ingest (automatically excludes connection_requests)
python -m src.main --mode database --table linkedin_db_raw_linkedin_ingest --max-connections 10

# Dry run (no actual actions)
python -m src.main --dry-run
```

## Project Structure

```
linkedin-automation/
├── src/
│   ├── main.py              # Entry point
│   ├── browser/
│   │   ├── browser.py       # Browser automation engine
│   │   ├── antidetect.py    # Anti-detection mechanisms
│   │   └── humanize.py      # Human-like behavior
│   ├── auth/
│   │   ├── login.py         # Login functionality
│   │   ├── session.py       # Session management
│   │   └── checkpoint.py    # 2FA/captcha detection
│   ├── search/
│   │   ├── search.py        # User search
│   │   ├── parser.py        # Profile parser
│   │   └── pagination.py    # Pagination handler
│   ├── connection/
│   │   ├── connect.py       # Connection requests
│   │   ├── note.py          # Personalized notes
│   │   └── tracker.py       # Request tracking
│   ├── messaging/
│   │   ├── followup.py      # Follow-up messages
│   │   ├── template.py      # Template engine
│   │   └── tracker.py       # Message tracking
│   ├── database/
│   │   └── db.py            # Database connection and queries
│   └── utils/
│       ├── config.py        # Configuration
│       └── models.py        # Data models
├── configs/
│   └── config.yaml          # Configuration file
├── data/
│   ├── cookies/             # Session cookies
│   └── tracking/            # Request/message tracking
├── requirements.txt
└── README.md
```

## Rate Limits (Default)
- Daily connections: 25
- Daily messages: 50
- Min delay between actions: 2-5 seconds
- Page load delay: 3 seconds

## License
MIT - Educational Use Only
