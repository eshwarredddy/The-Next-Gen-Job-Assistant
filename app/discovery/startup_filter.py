import re
from typing import Optional, Tuple
from urllib.parse import urlparse

class StartupFilter:
    """Filter out job boards, recruitment agencies, and aggregator platforms
    while extracting canonical startup domains.
    """
    
    AGGREGATOR_DOMAINS = {
        "builtin.com", "ashbyhq.com", "lever.co", "greenhouse.io", "workable.com",
        "linkedin.com", "wellfound.com", "angel.co", "ycombinator.com", "ycombinator.org",
        "unojobs.com", "cutshort.io", "hirist.tech", "peerlist.io", "internshala.com",
        "naukri.com", "indeed.com", "glassdoor.com", "foundit.in", "sourcingxpress.com",
        "getmereferred.com", "zerogtalent.com", "jobboard.co.in"
    }
    
    @classmethod
    def clean_domain(cls, url_or_domain: str) -> str:
        if not url_or_domain:
            return ""
        if "://" not in url_or_domain:
            url_or_domain = f"https://{url_or_domain}"
        parsed = urlparse(url_or_domain)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        # Remove trailing slashes or ports
        domain = netloc.split(":")[0].strip()
        return domain
    
    @classmethod
    def is_job_board_or_aggregator(cls, domain: str) -> bool:
        clean = cls.clean_domain(domain)
        for agg in cls.AGGREGATOR_DOMAINS:
            if clean == agg or clean.endswith(f".{agg}"):
                return True
        return False
    
    @classmethod
    def normalize_company_name(cls, raw_title_or_name: str) -> str:
        """Strip aggregator junk like 'Data Scientist at X | BuiltIn' -> 'X'."""
        if not raw_title_or_name:
            return "Startup"
        name = raw_title_or_name
        # Remove pipes and dashes from page titles
        for delim in [" | ", " - ", " – ", " — "]:
            if delim in name:
                parts = name.split(delim)
                # Usually company or job title
                name = parts[0]
        # Remove phrases like 'Hiring', 'Careers', 'Jobs'
        name = re.sub(r"(?i)\b(is hiring|hiring for|careers|jobs|job|vacancies)\b.*", "", name)
        name = re.sub(r"(?i)^(Senior|Lead|Junior|Associate)?\s*(Data Scientist|ML Engineer|Software Engineer|Founding Engineer)\s+(at|for)\s+", "", name)
        return name.strip() or "Startup"
