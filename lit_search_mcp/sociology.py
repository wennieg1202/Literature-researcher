"""
Sociology theory perspectives with seed terms for search query augmentation.
"""

PERSPECTIVES = {
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
            "Meyer Rowan institutionalized organizations",
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
            "Blumer symbolic interaction",
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
            "economic capital social capital", "status attainment",
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
            "social construction of reality",
        ],
        "seed_terms": [
            "sociology of knowledge Berger Luckmann", "social construction reality",
            "epistemic community", "Merton sociology science", "Kuhn paradigm",
            "Latour actor-network theory", "science technology society STS",
            "knowledge production sociology", "Mannheim knowledge sociology",
        ],
    },
}


def get_perspective_seeds(perspective: str) -> list[str]:
    """Return seed terms for a given perspective key."""
    if not perspective or perspective not in PERSPECTIVES:
        return []
    return PERSPECTIVES[perspective]["core_concepts"] + PERSPECTIVES[perspective]["seed_terms"]


def get_perspective_label(perspective: str) -> str:
    if not perspective or perspective not in PERSPECTIVES:
        return ""
    return PERSPECTIVES[perspective]["label"]
