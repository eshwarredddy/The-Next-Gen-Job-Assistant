# HireX AI - Autonomous Startup Recruiter

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Telegram API](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

An autonomous Telegram bot that acts as your personal "casting director" and recruiter. It automatically searches for early-stage startup founders in your desired location (e.g., Hyderabad, Bangalore, Chennai), cross-references their problem statement with your exact skills/resume, and drafts highly personalized, engineer-to-founder cold emails.

## Features

- **Autonomous Sourcing**: Finds AI and Tech startup founders using DuckDuckGo X-Ray searches and LLM Domain Targeting.
- **Strict Location Guardrails**: Enforces location constraints to ensure it only targets startups in your preferred cities (e.g., India-based startups).
- **Intelligent Pattern Matching**: Uses a two-step LLM pipeline (Casting Director + Scriptwriter).
  - The "Casting Director" reads the startup's problem statement and extracts the exact 1-2 projects from your resume that solve it.
  - If the startup's domain doesn't match your skills, it instantly drops the lead (`NO_MATCH`).
- **Verified Emails**: Uses the Hunter.io API to mathematically verify the founder's corporate email before drafting.
- **Engineer-to-Founder Tone**: Drafts short, punchy, no-nonsense emails explicitly avoiding corporate "recruiter-speak" or generic certifications.
- **Human-in-the-Loop**: Presents the drafted email to you in Telegram with inline buttons to either Send (via Gmail) or Skip.

## Prerequisites


- Python 3.9+
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- A Hunter.io API Key (from [Hunter.io](https://hunter.io/))
- An OpenRouter or OpenAI API Key for the `llama-3.1-8b-instruct` model

## Installation

1. Clone the repository:
   ```bash
   git clone <your-repo-url>
   cd sidedoor-ai
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # On Windows
   pip install -r requirements.txt
   ```

3. Set up your environment variables by creating a `.env` file in the root directory:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_token
   HUNTER_API_KEY=your_hunter_api_key
   LLM_API_KEY=your_llm_api_key
   LLM_BASE_URL=https://openrouter.ai/api/v1  # Or standard OpenAI URL
   ```

## Usage: Running the Job & Email Drafting Agent

1. Start the bot server:
   ```bash
   python main.py
   ```

2. Open Telegram and search for your bot.

3. Send `/start` to begin the onboarding process. The bot will ask for:
   - Your name
   - Your target roles (e.g., ML Engineer, Data Scientist)
   - Your target locations (e.g., Hyderabad, Bangalore)
   - Your resume (Upload as a PDF)

4. Once onboarding is complete, say something like `"Start searching!"`

5. The bot will autonomously run in the background. When it finds a verified founder email and successfully maps their product to your resume, it will send you a draft:
   ```text
   Sample Draft for Subrina at NeuralGarage:

   To: subrina@neuralgarage.com
   Subject: Exploring roles at NeuralGarage

   Hey Subrina,
   Saw NeuralGarage made TechCrunch...
   ```

6. Click **✅ Send via Gmail** to fire off the email, or **❌ Skip** to discard the draft and have the bot find a new lead.

## Tech Stack
- **Python-Telegram-Bot**: For the async Telegram interface.
- **SQLAlchemy (SQLite)**: For local state, chat history, and deduplication tracking.
- **OpenAI Python SDK**: For querying Llama-3.1-8b via OpenRouter.
- **DuckDuckGo-Search (ddgs)**: For X-Ray targeting.
- **PyPDF2**: For parsing uploaded resumes.
- **Exa**: For web scraping
- **OpenRouter**: Used as LLM
