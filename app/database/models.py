from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    domain = Column(String, unique=True, index=True, nullable=False)
    location = Column(String, default="India")
    description = Column(Text, default="")
    research_data = Column(Text, default="")
    stage = Column(String, default="Unknown")  # Seed, Series A, Bootstrapped, Unknown
    status = Column(String, default="DISCOVERED") # DISCOVERED, QUALIFIED, RESEARCHED, SUPPRESSED
    created_at = Column(DateTime, default=datetime.utcnow)
    
    contacts = relationship("Founder", back_populates="company", cascade="all, delete-orphan")
    evidence = relationship("CompanyEvidence", back_populates="company", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="company")

class CompanyEvidence(Base):
    __tablename__ = "company_evidence"
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source_url = Column(String, nullable=False)
    page_title = Column(String, default="")
    extracted_claim = Column(Text, nullable=False)
    evidence_type = Column(String, default="product") # product, hiring, tech_stack, leadership
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="evidence")

class Founder(Base):
    """Normalized Contact entity (founder, CTO, tech lead, engineering manager)."""
    __tablename__ = "founders"
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="Engineering Leader")
    email = Column(String, unique=True, index=True, nullable=False)
    email_verified = Column(Integer, default=0) # 0=unverified, 1=verified, 2=high_confidence
    contact_source = Column(String, default="hunter") # hunter, apollo, crawl4ai, manual
    verification_score = Column(Float, default=0.0)
    is_suppressed = Column(Boolean, default=False)
    suppression_reason = Column(String, nullable=True) # opt_out, bounce, decline, manual
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="contacts")
    opportunities = relationship("Opportunity", back_populates="founder")

class Opportunity(Base):
    __tablename__ = "opportunities"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    founder_id = Column(Integer, ForeignKey("founders.id"), nullable=False)
    match_score = Column(Integer, default=50)
    opportunity_reason = Column(Text, default="")
    potential_role = Column(String, default="Software Engineer")
    status = Column(String, default="discovered") # discovered, matched, approved, sent, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="opportunities")
    founder = relationship("Founder", back_populates="opportunities")
    outreach = relationship("Outreach", back_populates="opportunity", uselist=False)

class Outreach(Base):
    __tablename__ = "outreach"
    
    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), unique=True, nullable=False)
    
    # Framework metadata
    framework = Column(String, default="CASUAL_INTRODUCTION") # PAIN_POINT, PRODUCT_ANALYSIS, PROOF_OF_WORK, CASUAL_INTRODUCTION
    selected_project_ids = Column(String, default="[]") # JSON list of matched candidate project keys
    candidate_evidence = Column(Text, default="")
    
    email_subject = Column(String, nullable=False)
    email_body = Column(Text, nullable=False)
    
    # Delivery & Tracking
    gmail_message_id = Column(String, nullable=True, index=True)
    gmail_thread_id = Column(String, nullable=True, index=True)
    sent_at = Column(DateTime, nullable=True)
    reply_received_at = Column(DateTime, nullable=True)
    reply_classification = Column(String, nullable=True) # human_positive, human_negative, opt_out, ooo, auto_reply, bounce
    
    # Sequence state
    followup_count = Column(Integer, default=0)
    next_followup_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending") # pending, approved, sent, replied, bounced, completed, skipped, cancelled
    
    opportunity = relationship("Opportunity", back_populates="outreach")
    scheduled_actions = relationship("ScheduledFollowup", back_populates="outreach", cascade="all, delete-orphan")

class ScheduledFollowup(Base):
    __tablename__ = "scheduled_followups"
    
    id = Column(Integer, primary_key=True)
    outreach_id = Column(Integer, ForeignKey("outreach.id", ondelete="CASCADE"), nullable=False)
    step_number = Column(Integer, nullable=False) # 1 = Day 3, 2 = Day 7
    scheduled_time = Column(DateTime, nullable=False, index=True)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    
    # Generation details
    generated_subject = Column(String, nullable=True)
    generated_body = Column(Text, nullable=True)
    
    status = Column(String, default="PENDING") # PENDING, SENT, CANCELLED, FAILED, SKIPPED
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    outreach = relationship("Outreach", back_populates="scheduled_actions")

class SuppressionRecord(Base):
    __tablename__ = "suppression_records"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    domain = Column(String, index=True, nullable=True)
    reason = Column(String, nullable=False) # opt_out, bounce, decline, manual
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class ActiveUser(Base):
    __tablename__ = 'active_users'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, unique=True, index=True)
    candidate_name = Column(String, nullable=True)
    resume_text = Column(Text, nullable=True)
    extracted_roles = Column(Text, nullable=True)
    extracted_skills = Column(Text, nullable=True)
    extracted_projects = Column(Text, nullable=True)
    target_location = Column(String, default="Hyderabad")
    preferences = Column(String, nullable=True)
    last_search = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)

class SystemMetric(Base):
    __tablename__ = "system_metrics"
    id = Column(Integer, primary_key=True)
    metric_name = Column(String, index=True, nullable=False)
    metric_value = Column(Float, default=1.0)
    metadata_json = Column(Text, default="{}")
    recorded_at = Column(DateTime, default=datetime.utcnow)
