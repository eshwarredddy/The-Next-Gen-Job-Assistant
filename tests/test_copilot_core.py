import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import (
    Base, Company, Founder, Opportunity, Outreach, ScheduledFollowup
)
from app.discovery.startup_filter import StartupFilter
from app.matching.project_registry import get_project, list_all_projects
from app.matching.project_scorer import ProjectScorer
from app.outreach.framework_selector import OutreachFrameworkSelector
from app.outreach.followup_service import FollowupService

def test_startup_filter_aggregators():
    """Verify aggregator/job-board domains are identified and rejected."""
    assert StartupFilter.is_job_board_or_aggregator("jobs.lever.co") is True
    assert StartupFilter.is_job_board_or_aggregator("greenhouse.io") is True
    assert StartupFilter.is_job_board_or_aggregator("unojobs.com") is True
    assert StartupFilter.is_job_board_or_aggregator("internshala.com") is True
    assert StartupFilter.is_job_board_or_aggregator("neuralgarage.com") is False
    assert StartupFilter.is_job_board_or_aggregator("clodura.ai") is False

def test_company_name_normalization():
    """Verify company names are cleaned of ATS listing prefixes and pipes."""
    assert StartupFilter.normalize_company_name("Founding Engineer at Stealth AI | Lever") == "Stealth AI"
    assert StartupFilter.normalize_company_name("Data Scientist Work From Home Fresher Job") == "Data Scientist Work From Home Fresher"
    assert StartupFilter.normalize_company_name("NeuralGarage - GenAI Dubbing") == "NeuralGarage"

def test_project_registry_integrity():
    """Verify verified candidate projects exist with valid schemas."""
    projects = list_all_projects()
    assert len(projects) >= 4
    datachat = get_project("datachat")
    assert datachat is not None
    assert "LangChain" in datachat.technologies
    assert "nlp" in get_project("fake_job_detection").domains

def test_project_scoring_domain_affinity():
    """Verify scoring engine matches fraud/classification companies to Fake Job Detection
    and tabular/conversational companies to DataChat.
    """
    fake_job_proj = get_project("fake_job_detection")
    datachat_proj = get_project("datachat")
    
    score_fraud, signals_fraud = ProjectScorer.score_project(
        fake_job_proj,
        company_text="We build real-time fraud detection and risk anomaly systems",
        role_title="ML Engineer"
    )
    score_datachat, _ = ProjectScorer.score_project(
        datachat_proj,
        company_text="We build real-time fraud detection and risk anomaly systems",
        role_title="ML Engineer"
    )
    assert score_fraud > score_datachat
    assert any("Domain overlap" in s for s in signals_fraud)

def test_framework_selection_logic():
    """Verify dynamic framework selection based on scores and signals."""
    datachat = get_project("datachat")
    
    # Low relevance -> NOT_TO_SEND
    fw, reason = OutreachFrameworkSelector.select_framework(
        "Construction Co", "We pour concrete", datachat, match_score=0.1
    )
    assert fw == "NOT_TO_SEND"
    
    # Specific tech challenge -> PAIN_POINT
    fw, _ = OutreachFrameworkSelector.select_framework(
        "FinTech AI", "Handling risk anomaly detection", datachat, match_score=0.55, has_specific_tech_challenge=True
    )
    assert fw == "PAIN_POINT"
    
    # High match score -> PROOF_OF_WORK
    fw, _ = OutreachFrameworkSelector.select_framework(
        "Analytics AI", "Building natural language BI tools", datachat, match_score=0.45
    )
    assert fw == "PROOF_OF_WORK"

def test_followup_scheduling_and_cancellation():
    """Test that Day 3 and Day 7 follow-ups are automatically scheduled in the DB,
    and cancelled upon reply.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    company = Company(name="TestStartup", domain="teststartup.io")
    db_session.add(company)
    db_session.commit()
    
    founder = Founder(company_id=company.id, name="Jane Doe", email="jane@teststartup.io")
    db_session.add(founder)
    db_session.commit()
    
    opp = Opportunity(company_id=company.id, founder_id=founder.id)
    db_session.add(opp)
    db_session.commit()
    
    outreach = Outreach(
        opportunity_id=opp.id,
        email_subject="Test Subject",
        email_body="Test Body",
        status="sent",
        sent_at=datetime.utcnow()
    )
    db_session.add(outreach)
    db_session.commit()
    
    proj = get_project("datachat")
    FollowupService.schedule_sequence(db_session, outreach, proj)
    
    # Verify 2 actions scheduled
    actions = db_session.query(ScheduledFollowup).filter(ScheduledFollowup.outreach_id == outreach.id).all()
    assert len(actions) == 2
    assert actions[0].step_number == 1
    assert actions[1].step_number == 2
    assert actions[0].status == "PENDING"
    
    # Simulate reply event -> cancels follow-ups
    cancelled = FollowupService.cancel_all_followups(db_session, outreach.id, reason="replied")
    assert cancelled == 2
    
    actions_after = db_session.query(ScheduledFollowup).filter(ScheduledFollowup.outreach_id == outreach.id).all()
    assert all(a.status == "CANCELLED" for a in actions_after)
    
    refreshed = db_session.query(Outreach).filter(Outreach.id == outreach.id).first()
    assert refreshed.status == "replied"
    db_session.close()
