"""
Research perspectives library.

Built-in perspectives cover sociology, political science, economics,
psychology, gender studies, postcolonial theory, and more.

Custom perspectives added via add_perspective() are persisted in
perspectives_custom.json alongside this file and merged at import time.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict

log = logging.getLogger(__name__)

_CUSTOM_FILE = Path(__file__).parent / "perspectives_custom.json"

# ─── Built-in perspectives ────────────────────────────────────────────────────

_BUILTIN: Dict[str, dict] = {
    # ── Sociology ──────────────────────────────────────────────────────────────
    "profession": {
        "label": "Profession & Expertise",
        "theorists": ["Abbott", "Freidson", "Larson", "Saks"],
        "core_concepts": [
            "professional work", "jurisdiction", "expertise", "professional project",
            "credentialism", "occupational closure", "professional autonomy",
            "professionalization", "deprofessionalization", "knowledge work",
        ],
        "seed_terms": [
            "profession sociology", "professional jurisdiction", "expert knowledge",
            "occupational closure", "professional autonomy", "Abbott system of professions",
            "Freidson professionalism", "credentialism", "professional project",
        ],
    },
    "organization": {
        "label": "Organizational Theory & Institutions",
        "theorists": ["DiMaggio", "Powell", "Meyer", "Rowan", "Selznick", "Scott"],
        "core_concepts": [
            "institutional theory", "isomorphism", "organizational field",
            "legitimacy", "institutional logics", "organizational ecology",
            "neo-institutionalism", "coercive mimetic normative", "loose coupling",
        ],
        "seed_terms": [
            "institutional theory organizations", "organizational isomorphism",
            "DiMaggio Powell institutional", "organizational legitimacy",
            "institutional logics", "neo-institutionalism", "organizational field",
        ],
    },
    "symbolic": {
        "label": "Symbolic Interaction & Cultural Sociology",
        "theorists": ["Goffman", "Blumer", "Mead", "Becker", "Alexander"],
        "core_concepts": [
            "symbolic interaction", "meaning-making", "identity", "stigma",
            "framing", "presentation of self", "labeling theory",
            "cultural sociology", "narrative", "ritual",
        ],
        "seed_terms": [
            "symbolic interactionism", "Goffman presentation self", "identity construction",
            "meaning-making sociology", "framing theory", "stigma Goffman",
            "labeling theory deviance", "cultural sociology meaning",
        ],
    },
    "stratification": {
        "label": "Social Stratification & Inequality",
        "theorists": ["Bourdieu", "Wright", "Tilly", "Grusky", "Massey"],
        "core_concepts": [
            "social stratification", "capital", "habitus", "field", "class",
            "inequality", "social reproduction", "cultural capital",
            "economic capital", "social mobility", "durable inequality",
        ],
        "seed_terms": [
            "social stratification Bourdieu", "cultural capital habitus",
            "social reproduction inequality", "class analysis sociology",
            "durable inequality Tilly", "social mobility", "field theory Bourdieu",
        ],
    },
    "network": {
        "label": "Social Network Analysis",
        "theorists": ["Granovetter", "Burt", "White", "Wellman", "Watts"],
        "core_concepts": [
            "social network", "weak ties", "structural holes", "brokerage",
            "embeddedness", "social capital", "network closure", "tie strength",
            "small world", "community structure",
        ],
        "seed_terms": [
            "social network analysis", "Granovetter weak ties", "structural holes Burt",
            "network embeddedness", "social capital networks", "tie strength",
            "brokerage network", "community detection", "network closure",
        ],
    },
    "knowledge": {
        "label": "Sociology of Knowledge & Science",
        "theorists": ["Berger", "Luckmann", "Mannheim", "Merton", "Latour"],
        "core_concepts": [
            "sociology of knowledge", "social construction", "epistemic community",
            "scientific community", "paradigm", "knowledge production",
            "actor-network theory", "science technology society",
        ],
        "seed_terms": [
            "sociology of knowledge Berger Luckmann", "social construction reality",
            "epistemic community", "Merton sociology science", "Kuhn paradigm",
            "Latour actor-network theory", "science technology society STS",
        ],
    },
    # ── Gender & Intersectionality ─────────────────────────────────────────────
    "feminist": {
        "label": "Feminist Theory & Gender Studies",
        "theorists": ["Butler", "Collins", "hooks", "Haraway", "Crenshaw"],
        "core_concepts": [
            "gender", "intersectionality", "patriarchy", "feminism",
            "gender performativity", "standpoint theory", "care ethics",
            "reproductive labor", "gender inequality", "sexism",
        ],
        "seed_terms": [
            "feminist theory", "gender studies", "intersectionality Crenshaw",
            "Butler gender performativity", "Collins Black feminist thought",
            "care ethics gender", "feminist standpoint theory",
            "gender inequality labor", "reproductive work",
        ],
    },
    # ── Political Science & Governance ────────────────────────────────────────
    "governance": {
        "label": "Political Science & Governance",
        "theorists": ["Foucault", "Habermas", "Ostrom", "March", "Olsen"],
        "core_concepts": [
            "governance", "power", "policy", "state", "public administration",
            "bureaucracy", "deliberative democracy", "regulation", "welfare state",
            "political institutions", "collective action",
        ],
        "seed_terms": [
            "governance policy", "Foucault power discourse", "Habermas public sphere",
            "Ostrom commons governance", "bureaucracy state", "welfare state policy",
            "regulatory governance", "political institutions", "public administration",
        ],
    },
    # ── Economics & Political Economy ─────────────────────────────────────────
    "political_economy": {
        "label": "Political Economy & Economic Sociology",
        "theorists": ["Polanyi", "Piore", "Sabel", "Hall", "Soskice"],
        "core_concepts": [
            "political economy", "capitalism", "labor market", "commodification",
            "varieties of capitalism", "embeddedness", "market institutions",
            "economic inequality", "financialization", "globalization",
        ],
        "seed_terms": [
            "political economy", "Polanyi embeddedness market", "varieties of capitalism",
            "labor market institutions", "commodification Polanyi", "financialization",
            "economic sociology", "Hall Soskice varieties capitalism",
            "globalization inequality",
        ],
    },
    # ── Psychology & Behavior ─────────────────────────────────────────────────
    "psychology": {
        "label": "Social & Organizational Psychology",
        "theorists": ["Bandura", "Tajfel", "Turner", "Seligman", "Kahneman"],
        "core_concepts": [
            "social cognition", "identity", "self-efficacy", "motivation",
            "social identity theory", "cognitive bias", "group dynamics",
            "organizational behavior", "burnout", "psychological safety",
        ],
        "seed_terms": [
            "social identity theory Tajfel", "self-efficacy Bandura",
            "cognitive bias decision-making", "organizational psychology",
            "burnout work stress", "psychological safety", "group dynamics",
            "motivation self-determination theory",
        ],
    },
    # ── Postcolonial & Critical Theory ────────────────────────────────────────
    "postcolonial": {
        "label": "Postcolonial & Decolonial Theory",
        "theorists": ["Said", "Spivak", "Bhabha", "Fanon", "Quijano"],
        "core_concepts": [
            "colonialism", "postcolonialism", "decolonization", "subaltern",
            "othering", "hybridity", "coloniality of power", "Orientalism",
            "Global South", "epistemic violence",
        ],
        "seed_terms": [
            "postcolonial theory Said Orientalism", "Spivak subaltern",
            "Bhabha hybridity", "decolonial theory Quijano",
            "coloniality of power", "Global South knowledge",
            "epistemic violence", "decolonizing research",
        ],
    },
    # ── Historical & Comparative ──────────────────────────────────────────────
    "historical": {
        "label": "Historical & Comparative Institutionalism",
        "theorists": ["Thelen", "Streeck", "Mahoney", "Pierson", "Skocpol"],
        "core_concepts": [
            "path dependency", "historical institutionalism", "critical juncture",
            "institutional change", "layering", "conversion", "drift",
            "comparative historical analysis", "welfare state development",
        ],
        "seed_terms": [
            "path dependency historical institutionalism", "Thelen institutional change",
            "critical juncture", "Pierson increasing returns",
            "comparative historical analysis", "welfare state development",
            "institutional layering drift conversion",
        ],
    },
    # ── STS / Technology ──────────────────────────────────────────────────────
    "sts": {
        "label": "Science, Technology & Society (STS)",
        "theorists": ["Bijker", "Pinch", "Jasanoff", "Winner", "Haraway"],
        "core_concepts": [
            "social construction of technology", "SCOT", "co-production",
            "sociotechnical imaginaries", "technological determinism",
            "innovation systems", "responsible innovation", "AI ethics",
            "platform governance", "algorithmic accountability",
        ],
        "seed_terms": [
            "social construction technology SCOT", "Jasanoff sociotechnical imaginaries",
            "co-production science society", "algorithmic accountability",
            "AI ethics governance", "platform society", "responsible innovation",
            "technological determinism", "innovation systems",
        ],
    },
}


# ─── Custom perspectives (persisted to disk) ─────────────────────────────────

def _load_custom() -> Dict[str, dict]:
    if _CUSTOM_FILE.exists():
        try:
            return json.loads(_CUSTOM_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Failed to load perspectives_custom.json: %s", e)
    return {}


def _save_custom(custom: Dict[str, dict]) -> None:
    _CUSTOM_FILE.write_text(
        json.dumps(custom, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _all_perspectives() -> Dict[str, dict]:
    """Merge built-in + custom; custom wins on key collision."""
    merged = dict(_BUILTIN)
    merged.update(_load_custom())
    return merged


# ─── Public API ───────────────────────────────────────────────────────────────

def get_perspective_seeds(perspective: str) -> list[str]:
    all_p = _all_perspectives()
    if not perspective or perspective not in all_p:
        return []
    p = all_p[perspective]
    return p.get("core_concepts", []) + p.get("seed_terms", [])


def get_perspective_label(perspective: str) -> str:
    all_p = _all_perspectives()
    if not perspective or perspective not in all_p:
        return ""
    return all_p[perspective].get("label", perspective)


def list_perspectives() -> Dict[str, str]:
    """Return {key: label} for all known perspectives."""
    return {k: v.get("label", k) for k, v in _all_perspectives().items()}


def save_perspective(
    key: str,
    label: str,
    theorists: list[str],
    core_concepts: list[str],
    seed_terms: list[str],
) -> bool:
    """
    Persist a new (or updated) perspective to perspectives_custom.json.
    Returns True on success.
    """
    key = key.strip().lower().replace(" ", "_")
    custom = _load_custom()
    custom[key] = {
        "label": label,
        "theorists": theorists,
        "core_concepts": core_concepts,
        "seed_terms": seed_terms,
    }
    try:
        _save_custom(custom)
        log.info("Saved perspective '%s' to %s", key, _CUSTOM_FILE)
        return True
    except Exception as e:
        log.warning("Failed to save perspective '%s': %s", key, e)
        return False
