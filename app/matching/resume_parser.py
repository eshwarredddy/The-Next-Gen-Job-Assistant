import json
import re
from typing import Dict, Any, List
from app.intelligence.llm_router import llm_router
from app.matching.project_registry import VerifiedProject

class ResumeParser:
    """Dynamically parses candidate resumes into structured skills, projects, and target roles."""
    
    @classmethod
    async def parse_resume_to_profile(cls, resume_text: str) -> Dict[str, Any]:
        prompt = f"""
Analyze the following resume text and extract the candidate's structured technical profile.

Resume Text:
{resume_text[:4000]}

Extract:
1. "candidate_name": Full name of candidate.
2. "target_roles": List of 2-3 technical job titles this candidate qualifies for (e.g., ["Data Science / ML Engineer", "Backend Engineer"]).
3. "top_skills": List of primary languages, frameworks, and technical skills found in resume.
4. "projects": List of projects found in the resume. For each project, extract:
   - "project_id": Short alphanumeric slug (e.g. "datachat", "fraud_classifier")
   - "name": Full project name
   - "summary": 1-2 sentence summary of what it does
   - "domains": List of domain tags (e.g. ["nlp", "machine_learning", "data_analytics", "web_development"])
   - "capabilities": 2-3 key capabilities demonstrated
   - "technologies": List of tech used (e.g. ["Python", "Flask", "React"])
   - "verifiable_accomplishments": 1 sentence describing accuracy, features built, or metric
   - "implementation_status": "Implemented"
   - "evidence_notes": "Extracted from candidate resume"

DO NOT INVENT PROJECTS NOT IN THE RESUME.

Return ONLY a valid JSON object matching this structure:
{{
  "candidate_name": "...",
  "target_roles": ["..."],
  "top_skills": ["..."],
  "projects": [
     {{
        "project_id": "...",
        "name": "...",
        "summary": "...",
        "domains": ["..."],
        "capabilities": ["..."],
        "technologies": ["..."],
        "verifiable_accomplishments": "...",
        "implementation_status": "Implemented",
        "evidence_notes": "Extracted from uploaded resume"
     }}
  ]
}}
"""
        raw = await llm_router.complete(prompt, temperature=0.1)
        # Parse JSON safely
        try:
            return json.loads(raw, strict=False)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0), strict=False)
                except Exception:
                    pass
                    
        return {
            "candidate_name": "Candidate",
            "target_roles": ["Software Engineer", "Data Scientist"],
            "top_skills": ["Python", "SQL", "Machine Learning"],
            "projects": []
        }

    @classmethod
    def convert_to_verified_projects(cls, projects_data: List[Dict[str, Any]]) -> List[VerifiedProject]:
        projects = []
        for p in projects_data:
            try:
                proj = VerifiedProject(
                    project_id=p.get("project_id", "project"),
                    name=p.get("name", "Project"),
                    summary=p.get("summary", ""),
                    domains=p.get("domains", ["engineering"]),
                    capabilities=p.get("capabilities", []),
                    technologies=p.get("technologies", ["Python"]),
                    implemented_features=p.get("capabilities", []),
                    verifiable_accomplishments=p.get("verifiable_accomplishments", ""),
                    implementation_status="Implemented",
                    evidence_notes=p.get("evidence_notes", "Extracted from uploaded resume")
                )
                projects.append(proj)
            except Exception as e:
                print(f"[ResumeParser] Error constructing VerifiedProject: {e}")
        return projects
