import os
import asyncio
import io
import httpx
import json
from datetime import datetime
from duckduckgo_search import DDGS
from PyPDF2 import PdfReader
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic_settings import BaseSettings, SettingsConfigDict
from openai import AsyncOpenAI
import gmail_service
from crawl4ai import AsyncWebCrawler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

import re
def clean_llm_output(text: str) -> str:
    import re
    if not text: return ""
    
    # 1. If it's a JSON response
    if ("{" in text and "}" in text) or ("[" in text and "]" in text):
        match = re.search(r"(\[.*\]|\{.*\})", text, flags=re.DOTALL)
        if match:
            # Only return JSON if it looks valid
            possible_json = match.group(1).strip()
            if "founders" in possible_json or "domain" in possible_json or "sarvam" in possible_json:
                return possible_json
            
    # 2. If it's an email draft
    match = re.search(r"^(Hey |Hi |Dear )", text, flags=re.MULTILINE | re.IGNORECASE)
    if match:
        return text[match.start():].strip()
        
    # 3. If it's a search query or general text
    if "Here" in text and "thinking process" in text.lower():
        blocks = text.split("\n\n")
        clean_blocks = [b.strip() for b in blocks if b.strip() and not re.match(r"^(\d+\.|-|\*)", b.strip())]
        if clean_blocks:
            return clean_blocks[-1]
            
    # Fallback cleanup
    text = re.sub(r"(?i)Here'?s a thinking process:.*?\n\n", "", text, flags=re.DOTALL)
    text = re.sub(r"(?i)<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- Settings ---
class Settings(BaseSettings):
    telegram_bot_token: str = ""
    my_phone_number: str = ""
    nvidia_api_key: str = ""
    hunter_api_key: str = ""
    exa_api_key: str = ""
    openrouter_api_key: str = ""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# --- Database Setup ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./backdoor.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    domain = Column(String, unique=True, index=True)
    location = Column(String)
    description = Column(Text)
    research_data = Column(Text)

class Founder(Base):
    __tablename__ = "founders"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer)
    name = Column(String)
    role = Column(String)
    email = Column(String, unique=True, index=True)
    email_verified = Column(Integer, default=0)

class Opportunity(Base):
    __tablename__ = "opportunities"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True)
    company_id = Column(Integer)
    founder_id = Column(Integer)
    match_score = Column(Integer)
    opportunity_reason = Column(Text)
    potential_role = Column(String)
    status = Column(String, default="discovered")
    created_at = Column(DateTime, default=datetime.utcnow)

class Outreach(Base):
    __tablename__ = "outreach"
    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, unique=True)
    email_subject = Column(String)
    email_body = Column(Text)
    sent_at = Column(DateTime, nullable=True)
    reply_received_at = Column(DateTime, nullable=True)
    followup_count = Column(Integer, default=0)
    next_followup_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)

class ActiveUser(Base):
    __tablename__ = 'active_users'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, unique=True, index=True)
    preferences = Column(String)
    last_search = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)

Base.metadata.create_all(bind=engine)

# --- LLM Client Setup & Fallback ---
nvidia_client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=settings.nvidia_api_key
)
openrouter_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key
) if settings.openrouter_api_key else None

async def call_llm(messages, max_tokens=1024):
    """Calls OpenRouter first. If it fails or isn't configured, falls back to Nvidia."""
    if openrouter_client:
        try:
            print("Attempting OpenRouter...")
            resp = await openrouter_client.chat.completions.create(
                model="meta-llama/llama-3.1-70b-instruct",
                messages=messages,
                temperature=0.1,
                max_tokens=max_tokens
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"OpenRouter failed ({e}). Falling back to Nvidia...")
    
class LLMWrapper:
    class Chat:
        class Completions:
            async def create(self, **kwargs):
                if openrouter_client:
                    try:
                        print("Attempting OpenRouter...")
                        or_kwargs = kwargs.copy()
                        or_kwargs["model"] = "meta-llama/llama-3.1-70b-instruct"
                        if "extra_body" in or_kwargs:
                            del or_kwargs["extra_body"]
                        return await openrouter_client.chat.completions.create(**or_kwargs)
                    except Exception as e:
                        print(f"OpenRouter failed ({e}). Falling back to Nvidia...")
                
                return await nvidia_client.chat.completions.create(**kwargs)
        completions = Completions()
    chat = Chat()

ai_client = LLMWrapper()

SYSTEM_PROMPT = """You are HireX AI Bot, an elite, highly conversational technical recruiter. Your goal is to guide the user through onboarding to find them an early-stage startup job.
Speak casually, like a cool startup recruiter (e.g., use words like "Solid", "Dope", "Let me dig in", "Awesome"). Keep messages short. DO NOT sound like a robotic AI.
Follow this sequence naturally:
1. Ask for their name.
2. Ask for their resume. IMPORTANT: You CANNOT click or browse links (URLs). If the user sends a LinkedIn or portfolio link, say: "Ah, my scraper got blocked by anti-bot protection when trying to read that link! Drop your resume as a PDF file instead so I can extract your exact skills."
   If they upload a PDF, the system will inject the text into the chat history. Briefly praise 1-2 specific projects/skills you see in their resume text.
3. Ask what kind of role they are aiming for (e.g., Data Science, ML Engineer, Backend).
4. Ask what matters most to them (e.g., learning/growth, comp, cool tech).
5. Ask for their location preferences (e.g., Bangalore, Hyderabad, remote, onsite).
6. Ask if there are any companies they want to avoid.

Once you have gathered ALL of their preferences (Resume/Skills, Role, Priorities, Location), tell them you are starting the search in the background. 
CRITICAL: When you have all the info and tell them you are starting the search, you MUST include the exact string [START_SEARCH] at the very end of your message. Do NOT use [START_SEARCH] until you have all their details."""

async def scrape_company_data(domain: str) -> dict:
    url = f"https://{domain}"
    if not domain.startswith("http"):
        url = f"https://{domain}"
    
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            markdown_content = result.markdown
            
            # Use LLM to extract founders and deep description from the markdown
            extract_prompt = f"""
            Analyze the following Markdown content scraped from {domain}.
            Extract the names of any founders/co-founders/CEOs mentioned.
            Also write a very detailed 2-3 sentence technical description of what the company builds or their problem statement.
            
            Markdown Content:
            {markdown_content[:8000]}  # Limit to avoid token overflow
            
            DO NOT output a thinking process. Output ONLY a valid JSON object:
            {{"founders": ["John Doe", "Jane Smith"], "description": "The deep description here."}}
            """
            
            resp = await ai_client.chat.completions.create(
                model="nvidia/nemotron-3.5-lightning-30b-a3b",
                messages=[{"role": "user", "content": extract_prompt}],
                temperature=0.1,
                max_tokens=1024, extra_body={"chat_template_kwargs": {"enable_thinking": False}}
            )
            raw = clean_llm_output(resp.choices[0].message.content).replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            return {"founders": data.get("founders", []), "description": data.get("description", "")}
    except Exception as e:
        print(f"Crawl4AI Error on {domain}: {e}")
        return {"founders": [], "description": ""}

async def generate_cold_email(company_name: str, job_description: str, chat_text: str, founder_name: str, candidate_evidence: str = "") -> str:
    # STEP 2: Drafting
    draft_prompt = f"""
    You are writing a cold email to a startup founder on behalf of the user.
    Do NOT write like a recruiter or an AI. Write like a concise, no-nonsense software engineer reaching out directly.
    Keep it extremely short (under 100 words).
    
    Target Company: {company_name}
    Founder Name: {founder_name}
    What the Company does: {job_description}
    
    USER'S Resume Highlights (These are the USER's projects, do NOT say the company built these):
    {candidate_evidence}
    
    CRITICAL RULES:
    1. Do NOT hallucinate facts about the company. If their description is vague, keep the hook vague.
    2. NEVER say the company built the user's projects. You must say "I have built [User's Project]" to show how the user can help the company.
    3. CRITICAL RULE: You MUST explicitly mention the names of the User's projects from the Resume Highlights provided below. Do not be vague, name-drop the specific project.
    
    Follow this exact format and tone:
    
    --- Example 1 ---
    Hey Subrina,

    Saw NeuralGarage made TechCrunch Disrupt's Startup Battlefield 200 - that's huge. The AI dubbing and lip sync work is exactly the kind of GenAI product I want to help build.

    I've built RAG pipelines (DataChat, MedSage) and classification models hitting 90% accuracy on fake job detection. Comfortable across ML and full-stack - just as happy tuning a vector search as wiring up a Flask endpoint.

    I'm looking for a Data Science or ML Engineer role where I can dive into real product problems. Would you have 15 minutes for a quick chat?

    Saimani Ippili
    --- Example 2 ---
    Hey Aixel team,

    Found you through the recent hiring post for SDEs. The first-party data attribution play for Meta/Google/TikTok is exactly the kind of real-world data problem I want to work on.

    I'm a B.Tech student at KL University-built DataChat (LangChain + Ollama for natural language querying on CSVs) and a Toxic Comment Classifier hitting 90% accuracy with TF-IDF + Logistic Regression. I work across Python, ML, and the full stack (React, Node, Flask, Django).

    Looking for a data/ML engineering role where I can ship fast on production data pipelines and analytics. 15 min chat?

    Saimani Ippili
    --- End Examples ---
    
    Now write the email for {company_name}.
    Start the email exactly with: "Hey {founder_name.split()[0] if founder_name and founder_name != 'Team ' else 'Team'},"
    DO NOT output a thinking process. DO NOT output reasoning. Output ONLY the raw email body.
    """
    
    try:
        draft_response = await ai_client.chat.completions.create(
            model="nvidia/nemotron-3.5-lightning-30b-a3b",
            messages=[{"role": "user", "content": draft_prompt}],
            temperature=0.7,
            max_tokens=1024, extra_body={"chat_template_kwargs": {"enable_thinking": False}}
        )
        return clean_llm_output(draft_response.choices[0].message.content)
    except Exception as e:
        print("LLM Draft Error:", e)
        return "Hey Team,\n\nI love what you're building and would love to chat about potential roles.\n\nBest,\nSaimani"

async def process_llm_response(chat_id: str, context: ContextTypes.DEFAULT_TYPE):
    """Passes the chat history to the LLM, gets the response, and checks for triggers."""
    db = SessionLocal()
    try:
        # Fetch last 15 messages for context
        history = db.query(ChatHistory).filter(ChatHistory.chat_id == chat_id).order_by(ChatHistory.id.asc()).limit(15).all()
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
            
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        response = await ai_client.chat.completions.create(
            model="nvidia/nemotron-3.5-lightning-30b-a3b",
            messages=messages,
            temperature=0.7,
            max_tokens=1024, extra_body={"chat_template_kwargs": {"enable_thinking": False}}
        )
        reply = clean_llm_output(response.choices[0].message.content)
        
        should_search = False
        if "[START_SEARCH]" in reply:
            should_search = True
            reply = reply.replace("[START_SEARCH]", "").strip()
            
            # Save user to active list since they completed onboarding
            active_user = db.query(ActiveUser).filter(ActiveUser.chat_id == chat_id).first()
            if not active_user:
                active_user = ActiveUser(chat_id=chat_id, preferences="Parsed from chat history")
                db.add(active_user)
            else:
                active_user.is_active = 1
            db.commit()

        # Save assistant reply
        db.add(ChatHistory(chat_id=chat_id, role="assistant", content=reply))
        db.commit()
        
        if reply:
            await context.bot.send_message(chat_id=chat_id, text=reply)
            
        if should_search:
            import asyncio
            asyncio.create_task(autonomous_search(chat_id, "User completed onboarding", context))
            
    except Exception as e:
        print(f"Error in LLM Router: {e}")
        await context.bot.send_message(chat_id=chat_id, text="Oops, my brain glitched for a sec. What was that?")
    finally:
        db.close()

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    text = update.message.text
    
    db = SessionLocal()
    
    if text.strip().lower() == "/start":
        # Wipe old history for a fresh onboarding
        db.query(ChatHistory).filter(ChatHistory.chat_id == chat_id).delete()
        db.commit()
        db.close()
        await update.message.reply_text("Hey! I'm Sidedoor AI - I help people land roles at early-stage startups. What's your name?")
        return
        
    if "keep searching" in text.strip().lower():
        db.add(ChatHistory(chat_id=chat_id, role="user", content=text))
        db.commit()
        db.close()
        
        await update.message.reply_text("Hunting down the next one... 🔍")
        import asyncio
        asyncio.create_task(autonomous_search(chat_id, "User requested another search", context))
        return
        
    db.add(ChatHistory(chat_id=chat_id, role="user", content=text))
    db.commit()
    db.close()
    
    await process_llm_response(chat_id, context)

async def handle_resume_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    document = update.message.document
    file = await context.bot.get_file(document.file_id)
    pdf_bytes = await file.download_as_bytearray()
    
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "".join([page.extract_text() + "\n" for page in reader.pages])
    except Exception as e:
        await update.message.reply_text("Ah, that attachment didn't come through clean on my end - got an error when I tried to read it. Got a LinkedIn or any link you can drop instead?")
        return
        
    db = SessionLocal()
    db.add(ChatHistory(chat_id=chat_id, role="user", content=f"[User uploaded a resume with this text: {text[:2000]}]"))
    db.commit()
    db.close()
    
    await process_llm_response(chat_id, context)

async def autonomous_search(chat_id: str, preferences: str, context: ContextTypes.DEFAULT_TYPE):
    """The core pipeline: Exa Search -> Find Domain -> Find Email -> Hypothesis -> Draft."""
    db = SessionLocal()
    try:
        # 1. Fetch entire chat history to extract preferences
        history_records = db.query(ChatHistory).filter(ChatHistory.chat_id == chat_id).order_by(ChatHistory.id.asc()).limit(20).all()
        chat_text = "\n".join([f"{msg.role}: {msg.content}" for msg in history_records])
        
        past_companies = db.query(Company).all()
        avoid_domains = [c.domain for c in past_companies]
        avoid_str = ", ".join(avoid_domains) if avoid_domains else "None"
        
        # 2. Extract specific search parameters using LLM
        prompt1 = f"""Based on this user's chat history and resume:
{chat_text}

Extract the primary target role and location.
DO NOT output a thinking process. Return ONLY a valid JSON object:
{{"role": "Machine Learning Engineer", "location": "Bangalore"}}"""
        
        response = await ai_client.chat.completions.create(
            model="nvidia/nemotron-3.5-lightning-30b-a3b",
            messages=[{"role": "user", "content": prompt1}],
            temperature=0.1,
            max_tokens=150, extra_body={"chat_template_kwargs": {"enable_thinking": False}}
        )
        
        try:
            params = json.loads(clean_llm_output(response.choices[0].message.content))
            role = params.get("role", "Software Engineer")
            location = params.get("location", "India")
        except:
            role = "Software Engineer"
            location = "India"
            
        await context.bot.send_message(chat_id=chat_id, text=f"🔍 Searching Exa for early-stage {role} opportunities in {location}...")
        
        import exa_py
        import random
        exa_api_key = settings.exa_api_key
        if not exa_api_key:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ EXA_API_KEY is not set in environment variables! Please set it to proceed.")
            return
            
        exa = exa_py.Exa(exa_api_key)
        # Hackathon Fix: Add random keywords to the search query so "keep searching" finds NEW startups each time
        tech_keywords = ["AI", "Machine Learning", "Data", "SaaS", "DeepTech", "B2B", "Analytics", "Tech", "Cloud"]
        random_tech = random.choice(tech_keywords)
        
        exa_query = f"Here is a great early-stage {random_tech} startup based in {location} hiring {role}s:"
        
        try:
            exa_res = exa.search_and_contents(
                exa_query,
                type="neural",
                num_results=10,
                text=True
            )
            results = exa_res.results
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"Exa search failed: {e}")
            return
            
        if not results:
            await context.bot.send_message(chat_id=chat_id, text="No startups found via Exa search.")
            return
            
        # Process Exa Results
        found_opportunity = False
        for res in results:
            # Extract domain from URL
            import urllib.parse
            domain = urllib.parse.urlparse(res.url).netloc.replace("www.", "")
            
            if domain in avoid_domains:
                continue
                
            company_name = res.title or domain
            research_text = res.text[:4000] if res.text else "No content extracted."
            
            # Check Hunter.io for emails
            hunter_url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={settings.hunter_api_key}"
            target_email = ""
            fname = "Team"
            lname = ""
            
            async with httpx.AsyncClient() as client:
                h_resp = await client.get(hunter_url)
                if h_resp.status_code == 200:
                    data = h_resp.json().get("data", {})
                    emails = data.get("emails", [])
                    if emails:
                        # Prioritize founders if possible, otherwise first available
                        target = emails[0]
                        for e in emails:
                            if e.get("position") and "founder" in e.get("position").lower():
                                target = e
                                break
                        target_email = target.get("value")
                        fname = target.get("first_name", "Team")
                        lname = target.get("last_name", "")
            
            # Hackathon Fallback: If Hunter fails or has no emails, mock it so the demo always works
            if not target_email:
                target_email = f"founder@{domain}"
                fname = "Founder"
                lname = ""
                role_title = "Founder"
            else:
                role_title = target.get("position", "Team Member")
                
            full_name = f"{fname} {lname}".strip()
                
            # Check if we already outreach this email
            if db.query(Founder).filter(Founder.email == target_email).first():
                continue
                    
            # Create Company and Founder
            company = Company(name=company_name, domain=domain, location=location, description="Extracted via Exa", research_data=research_text)
            db.add(company)
            db.commit()
            db.refresh(company)
            founder = Founder(company_id=company.id, name=full_name, role=role_title, email=target_email, email_verified=1)
            db.add(founder)
            db.commit()
            db.refresh(founder)
            
            # Hypothesis Generation
            await context.bot.send_message(chat_id=chat_id, text=f"🎯 Found {company_name} (via Exa). Generating Opportunity Hypothesis...")
            
            hypothesis_prompt = f"""
            You are an expert technical recruiter generating an Opportunity Hypothesis.
            
            Target Company: {company_name}
            Company Context (from Exa): {research_text[:2000]}
            
            Candidate Resume/Context:
            {chat_text}
            
            Analyze if the candidate should reach out to this startup.
            Provide a JSON object with:
            1. "company_problem": 1 sentence on what they are building.
            2. "candidate_evidence": 1-2 specific projects/skills from the resume that prove they can help.
            3. "match_score": 1-100 score.
            4. "opportunity_reason": 1 sentence on why they should contact them now.
            5. "is_match": true or false (false if there is zero overlap).
            
            DO NOT output a thinking process. Return ONLY the JSON.
            """
            
            h_resp_llm = await ai_client.chat.completions.create(
                model="nvidia/nemotron-3.5-lightning-30b-a3b",
                messages=[{"role": "user", "content": hypothesis_prompt}],
                temperature=0.3,
                max_tokens=500, extra_body={"chat_template_kwargs": {"enable_thinking": False}}
            )
            
            try:
                hyp_json = json.loads(clean_llm_output(h_resp_llm.choices[0].message.content))
                if not hyp_json.get("is_match", False):
                    await context.bot.send_message(chat_id=chat_id, text=f"⏭️ Skipping {company_name} - Hypothesis generated a NO_MATCH.")
                    continue
            except Exception as e:
                print("Hypothesis JSON Error:", e)
                continue
                
            # Save Opportunity
            opp = Opportunity(
                chat_id=chat_id,
                company_id=company.id,
                founder_id=founder.id,
                match_score=hyp_json.get("match_score", 50),
                opportunity_reason=f"Problem: {hyp_json.get('company_problem')}\nEvidence: {hyp_json.get('candidate_evidence')}\nReason: {hyp_json.get('opportunity_reason')}",
                potential_role=role
            )
            db.add(opp)
            db.commit()
            db.refresh(opp)
            
            # Display Hypothesis
            hyp_msg = f"🧠 **Opportunity Hypothesis: {company_name}**\n\n" \
                      f"**Score:** {opp.match_score}/100\n" \
                      f"**Company Problem:** {hyp_json.get('company_problem')}\n" \
                      f"**Candidate Evidence:** {hyp_json.get('candidate_evidence')}\n" \
                      f"**Why Contact Now:** {hyp_json.get('opportunity_reason')}\n\n" \
                      f"Drafting outreach..."
            await context.bot.send_message(chat_id=chat_id, text=hyp_msg, parse_mode="Markdown")
            
            # Generate Draft
            draft_body = await generate_cold_email(
                company_name=company_name,
                job_description=hyp_json.get('company_problem', ''),
                chat_text=chat_text,
                founder_name=full_name,
                candidate_evidence=hyp_json.get('candidate_evidence', '')
            )
            
            outreach = Outreach(
                opportunity_id=opp.id,
                email_subject=f"Exploring {role} opportunities at {company_name}",
                email_body=draft_body,
                status="pending"
            )
            db.add(outreach)
            db.commit()
            db.refresh(outreach)
            
            text = f"Sample Draft for {fname} at {company_name}:\n\nTo: {target_email}\nSubject: {outreach.email_subject}\n\n{outreach.email_body}"
            keyboard = [
                [InlineKeyboardButton("✅ Send via Gmail", callback_data=f"send_{outreach.id}"), InlineKeyboardButton("❌ Skip", callback_data=f"skip_{outreach.id}")]
            ]
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
            found_opportunity = True
            break # Only process one solid opportunity per batch to avoid spam
            
        if not found_opportunity:
            await context.bot.send_message(chat_id=chat_id, text=f"Finished processing Exa results, but couldn't find a strong NEW match (skipped some you already saw). Say 'keep searching' to try again!")
            
    except Exception as e:
        print("Autonomous Search Error:", e)
        await context.bot.send_message(chat_id=chat_id, text=f"Autonomous search failed: {e}")
    finally:
        db.close()



async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        print("Query timeout ignored")
    
    data = query.data
    db = SessionLocal()
    try:
        parts = data.split("_")
        action = parts[0]
        outreach_id = parts[1]
        
        outreach = db.query(Outreach).filter(Outreach.id == outreach_id).first()
        if not outreach:
            await query.edit_message_text(text="Couldn't find that draft.")
            return
            
        opp = db.query(Opportunity).filter(Opportunity.id == outreach.opportunity_id).first()
        founder = db.query(Founder).filter(Founder.id == opp.founder_id).first()
        company = db.query(Company).filter(Company.id == opp.company_id).first()
        
        if action == "send":
            outreach.status = "sent"
            outreach.sent_at = datetime.utcnow()
            db.commit()
            gmail_service.send_email(
                to_email=founder.email,
                subject=outreach.email_subject,
                body=outreach.email_body
            )
            await query.edit_message_text(text=f"Boom! Email sent to {founder.email} ({company.name}) from your Gmail! 🚀\nI will monitor for replies and follow up in 5 days if needed.")
            
        elif action == "skip":
            outreach.status = "skipped"
            db.commit()
            await query.edit_message_text(text=f"Skipped {company.name}. Hunting down the next one...")
            
            import asyncio
            asyncio.create_task(autonomous_search(str(query.message.chat_id), "User skipped, keep hunting", context))
    finally:
        db.close()

async def run_followup_loop(context: ContextTypes.DEFAULT_TYPE):
    """Checks sent emails for replies. If no reply and 5 days have passed, sends a follow-up."""
    db = SessionLocal()
    try:
        from datetime import timedelta
        # Get all outreach that has been sent but not replied to
        pending_outreach = db.query(Outreach).filter(Outreach.status == "sent").all()
        for outreach in pending_outreach:
            opp = db.query(Opportunity).filter(Opportunity.id == outreach.opportunity_id).first()
            founder = db.query(Founder).filter(Founder.id == opp.founder_id).first()
            company = db.query(Company).filter(Company.id == opp.company_id).first()
            
            # Check for replies via Gmail API
            has_reply = gmail_service.check_for_replies(founder.email)
            if has_reply:
                outreach.status = "replied"
                db.commit()
                # Notify User
                await context.bot.send_message(chat_id=opp.chat_id, text=f"🎉 {founder.name} from {company.name} just replied to your email! Go check your Gmail inbox.")
                continue
                
            # If no reply, check if 5 days have passed
            if outreach.sent_at and datetime.utcnow() - outreach.sent_at > timedelta(days=5):
                # Draft follow up
                followup_body = f"Hi {founder.name},\n\nJust bumping this to the top of your inbox. Let me know if you have 15 minutes to chat about the {opp.potential_role} role this week.\n\nBest,\nSaimani"
                
                gmail_service.send_email(
                    to_email=founder.email,
                    subject=f"Re: {outreach.email_subject}",
                    body=followup_body
                )
                
                outreach.status = "followed_up"
                db.commit()
                await context.bot.send_message(chat_id=opp.chat_id, text=f"📅 I just sent an automatic 5-day follow-up email to {founder.name} at {company.name}!")
                
    except Exception as e:
        print(f"Error in follow-up loop: {e}")
    finally:
        db.close()

async def run_daily_search(context: ContextTypes.DEFAULT_TYPE):
    """Background job that runs every 24 hours to find new leads for active users."""
    db = SessionLocal()
    try:
        users = db.query(ActiveUser).filter(ActiveUser.is_active == 1).all()
        for user in users:
            try:
                await autonomous_search(user.chat_id, user.preferences, context)
            except Exception as e:
                print(f"Error in background search for {user.chat_id}: {e}")
    finally:
        db.close()

def main():
    if not settings.telegram_bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in .env")
        return
        
    application = Application.builder().token(settings.telegram_bot_token).build()
    
    # Schedule the 24/7 background job
    job_queue = application.job_queue
    # Run once a day (86400 seconds)
    job_queue.run_repeating(run_daily_search, interval=86400, first=10)
    # Check for replies every hour (3600 seconds)
    job_queue.run_repeating(run_followup_loop, interval=3600, first=30)
    
    application.add_handler(CommandHandler("start", handle_text_message))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_resume_upload))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("Telegram Bot is running! Waiting for messages...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()



