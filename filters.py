"""Keyword/pattern rules for scoring Reddit threads.

Tuned from the user's r/msp comment history: MSP tooling, RMM/PSA,
M365/Azure governance, backup/DR, networking, security incidents,
Docker/Hyper-V, automation, and tech discussions.
"""
from __future__ import annotations

import re

# --- Subreddits to monitor ---
SUBREDDITS = [
    "aws",
    "cybersecurity",
    "docker",
    "HyperV",
    "ITCareerQuestions",
    "msp",
    "networking",
    "sysadmin",
    "technology",
    "techsupport",
    "ITManagers",
    "Office365",
    "AZURE",
    "k12sysadmin",
    "selfhosted",
    "homelab",
    "PowerShell",
    "sysadminjobs",
    "CompTIA",
]

# --- Title patterns that indicate a discussion/question opportunity ---
TITLE_PATTERNS = [
    r"\bhow (do|are|would|can|should) (you|i|we)\b",
    r"\banyone (else|using|tried|have|know)\b",
    r"\bis it just me\b",
    r"\bwhat('?s| is| are) (your|the best|the most)\b",
    r"\bbest (way|tool|practice|approach|option) (to|for)\b",
    r"\blooking for\b",
    r"\brecommend(ation)?s?\b",
    r"\balternatives? to\b",
    r"\bexperience(s)? with\b",
    r"\bthoughts on\b",
    r"\bopinions? on\b",
    r"\bhelp (with|me)\b",
    r"\bclient (wants|asking|demanding|insists)\b",
    r"\bhow to (handle|manage|deal with|approach|setup|configure)\b",
    r"\bany (good|recommended|reliable)\b",
    r"\bpros (and|&) cons\b",
    r"\bworth (it|switching|moving)\b",
    r"\bvs\.?\b",
    r"\?$",
]

# --- Topic keywords (case-insensitive substring match in title+selftext) ---
TOPIC_KEYWORDS = [
    # MSP / RMM / PSA
    "msp", "rmm", "psa", "ninja", "ninjaone", "connectwise", "datto", "kaseya",
    "syncro", "atera", "halopsa", "autotask", "n-able", "n-central",
    # M365 / Azure
    "m365", "microsoft 365", "office 365", "o365", "azure", "entra", "intune",
    "defender", "exchange online", "sharepoint", "teams admin", "global admin",
    "conditional access", "pim", "secure score",
    # Backup / DR
    "backup", "bdr", "veeam", "datto bcdr", "acronis", "wasabi", "immutab",
    "ransomware", "restore", "rpo", "rto", "air gap", "tape",
    # Networking
    "firewall", "fortinet", "fortigate", "palo alto", "sonicwall", "meraki",
    "unifi", "ubiquiti", "tp-link", "omada", "vlan", "vpn", "sd-wan",
    "switch", "router", "subnet", "dhcp", "dns",
    # Security
    "phishing", "mfa", "2fa", "edr", "siem", "soc", "vuln", "cve",
    "pentest", "audit", "compliance", "cis", "nist", "hipaa", "pci",
    "pingcastle", "nessus", "nmap",
    # Virtualization / containers
    "docker", "kubernetes", "k8s", "hyper-v", "hyperv", "vmware", "esxi",
    "proxmox", "container", "compose",
    # Automation / scripting
    "powershell", "automation", "script", "ansible", "terraform",
    # Hardware / endpoint
    "endpoint", "workstation", "server", "nas", "synology", "qnap",
    # Generic discussion fuel
    "tool", "stack", "workflow", "process", "policy", "vendor",
    "offboard", "onboard", "migration", "outage", "incident",
]

# --- Hard excludes (skip if any match title or flair) ---
EXCLUDE_PATTERNS = [
    r"\b(hiring|we'?re hiring|job posting|now hiring)\b",
    r"\b(meme|shitpost|rant|vent(ing)?)\b",
    r"\b(promo(tion)?|giveaway|launching|announcing my)\b",
    r"^\[?(hiring|for hire|job)\]?",
    r"\bmegathread\b",
    r"\bweekly (thread|discussion|question)\b",
    r"\bdaily (thread|discussion)\b",
]
EXCLUDE_FLAIRS = {
    "meme", "memes", "shitpost", "hiring", "for hire", "job posting",
    "promotion", "self-promotion", "announcement", "megathread",
}

_title_res = [re.compile(p, re.IGNORECASE) for p in TITLE_PATTERNS]
_exclude_res = [re.compile(p, re.IGNORECASE) for p in EXCLUDE_PATTERNS]


def is_excluded(title: str, flair: str | None) -> bool:
    if flair and flair.strip().lower() in EXCLUDE_FLAIRS:
        return True
    for rx in _exclude_res:
        if rx.search(title):
            return True
    return False


def score_thread(title: str, selftext: str, flair: str | None) -> int:
    """Return a relevance score. >=2 is considered an opportunity."""
    if is_excluded(title, flair):
        return 0

    score = 0
    text = f"{title}\n{selftext or ''}".lower()

    # Title pattern hits (strong signal)
    for rx in _title_res:
        if rx.search(title):
            score += 2
            break  # one pattern hit is enough

    # Topic keyword hits
    kw_hits = sum(1 for kw in TOPIC_KEYWORDS if kw in text)
    if kw_hits >= 1:
        score += 1
    if kw_hits >= 3:
        score += 1

    # Selftext present (real discussion, not just a link dump)
    if selftext and len(selftext.strip()) >= 80:
        score += 1

    return score
