"""Sociology theory lineage map.

Maps each sociological perspective to:
- key_theorists: canonical authors whose work anchors this tradition
- core_concepts: terms to inject into query expansion
- seed_terms: high-precision search phrases to add automatically
"""

from __future__ import annotations

PERSPECTIVES: dict[str, dict] = {
    "profession": {
        "label": "Professions & Expertise",
        "description": (
            "Sociology of professions, expert knowledge, credentialism, "
            "jurisdictional control, and professional projects."
        ),
        "key_theorists": [
            "Andrew Abbott", "Eliot Freidson", "Magali Sarfatti Larson",
            "Paul DiMaggio", "Steven Brint", "Everett Hughes",
            "Harold Wilensky", "Terence Johnson",
        ],
        "core_concepts": [
            "professional jurisdiction", "credentialism", "professional project",
            "expert knowledge", "licensed occupation", "professional autonomy",
            "deprofessionalization", "neo-professionalism", "knowledge work",
            "professional socialization", "professional identity",
        ],
        "seed_terms": [
            "sociology of professions",
            "professional jurisdiction Abbott",
            "professional project Larson",
            "expert knowledge Freidson",
        ],
        "canonical_works": [
            "Abbott 1988 System of Professions",
            "Freidson 1986 Professional Powers",
            "Larson 1977 Rise of Professionalism",
        ],
    },

    "organization": {
        "label": "Organizational Theory & Institutions",
        "description": (
            "Neo-institutional theory, resource dependence, population ecology, "
            "organizational fields, isomorphism, and institutional logics."
        ),
        "key_theorists": [
            "John Meyer", "Brian Rowan", "Paul DiMaggio", "Walter Powell",
            "Philip Selznick", "Charles Perrow", "Jeffrey Pfeffer",
            "Gerald Salancik", "Michael Hannan", "John Freeman",
            "Neil Fligstein", "Roger Friedland", "Robert Alford",
            "Patricia Thornton", "William Ocasio",
        ],
        "core_concepts": [
            "institutional isomorphism", "organizational field", "institutional logic",
            "resource dependence", "population ecology", "loose coupling",
            "mimetic isomorphism", "coercive isomorphism", "normative isomorphism",
            "organizational legitimacy", "decoupling", "institutional entrepreneurship",
            "inhabited institutions", "organizational identity",
        ],
        "seed_terms": [
            "neo-institutional theory organizations",
            "institutional isomorphism DiMaggio Powell",
            "organizational field sociology",
            "institutional logics Thornton Ocasio",
        ],
        "canonical_works": [
            "Meyer Rowan 1977 Institutionalized Organizations",
            "DiMaggio Powell 1983 Iron Cage Revisited",
            "Pfeffer Salancik 1978 External Control",
        ],
    },

    "symbolic": {
        "label": "Symbolic Interaction & Cultural Sociology",
        "description": (
            "Symbolic interactionism, dramaturgical analysis, cultural fields, "
            "habitus and capital, interaction ritual chains, and meaning-making."
        ),
        "key_theorists": [
            "Erving Goffman", "Pierre Bourdieu", "George Herbert Mead",
            "Herbert Blumer", "Randall Collins", "Ann Swidler",
            "Jeffrey Alexander", "Howard Becker", "Arlie Hochschild",
            "Eviatar Zerubavel", "Mustafa Emirbayer",
        ],
        "core_concepts": [
            "habitus", "cultural capital", "social field", "symbolic capital",
            "dramaturgical analysis", "impression management", "interaction ritual",
            "emotional energy", "cultural repertoire", "toolkit theory",
            "framing", "stigma", "total institution", "face-work",
            "collective memory", "boundary work", "cultural schema",
        ],
        "seed_terms": [
            "symbolic interactionism sociology",
            "Bourdieu habitus field capital",
            "Goffman interaction ritual",
            "cultural sociology meaning",
        ],
        "canonical_works": [
            "Goffman 1959 Presentation of Self",
            "Bourdieu 1984 Distinction",
            "Collins 2004 Interaction Ritual Chains",
            "Swidler 1986 Culture in Action",
        ],
    },

    "stratification": {
        "label": "Social Stratification & Inequality",
        "description": (
            "Class analysis, status attainment, mobility, intersectionality, "
            "cumulative advantage, and reproduction of inequality."
        ),
        "key_theorists": [
            "Erik Olin Wright", "Charles Tilly", "William Julius Wilson",
            "Annette Lareau", "Michele Lamont", "Patricia Hill Collins",
            "Douglas Massey", "Barbara Reskin", "David Grusky",
            "Samuel Bowles", "Herbert Gintis",
        ],
        "core_concepts": [
            "social class", "status attainment", "intergenerational mobility",
            "cumulative advantage", "intersectionality", "opportunity hoarding",
            "concerted cultivation", "cultural matching", "boundary formation",
            "categorical inequality", "durable inequality",
        ],
        "seed_terms": [
            "social stratification inequality sociology",
            "class analysis Wright",
            "durable inequality Tilly",
            "intersectionality Collins",
        ],
        "canonical_works": [
            "Tilly 1998 Durable Inequality",
            "Lareau 2003 Unequal Childhoods",
            "Lamont 1992 Money Morals Manners",
        ],
    },

    "network": {
        "label": "Social Networks & Relational Sociology",
        "description": (
            "Structural holes, weak ties, network embeddedness, social capital, "
            "relational sociology, and diffusion through networks."
        ),
        "key_theorists": [
            "Mark Granovetter", "Ronald Burt", "Nan Lin",
            "Barry Wellman", "Harrison White", "Mustafa Emirbayer",
            "David Knoke", "James Coleman", "Robert Putnam",
            "Nicholas Christakis", "James Fowler",
        ],
        "core_concepts": [
            "structural holes", "weak ties", "network embeddedness",
            "social capital", "brokerage", "closure", "diffusion",
            "network position", "tie strength", "triadic closure",
            "multiplex ties", "ego network", "whole network",
        ],
        "seed_terms": [
            "social network analysis sociology",
            "structural holes Burt",
            "strength of weak ties Granovetter",
            "social capital network",
        ],
        "canonical_works": [
            "Granovetter 1973 Strength of Weak Ties",
            "Burt 1992 Structural Holes",
            "Lin 2001 Social Capital",
        ],
    },

    "culture": {
        "label": "Culture, Knowledge & Cognition",
        "description": (
            "Sociology of knowledge, science and technology studies, "
            "cultural production, cognitive sociology, and epistemic communities."
        ),
        "key_theorists": [
            "Karl Mannheim", "Bruno Latour", "Steve Woolgar",
            "Harry Collins", "Robert Evans", "Karin Knorr Cetina",
            "Diane Vaughan", "Ezra Zuckerman", "Michèle Lamont",
            "Paul Dimaggio", "Omar Lizardo",
        ],
        "core_concepts": [
            "sociology of knowledge", "epistemic community", "social construction",
            "scientific field", "laboratory life", "trading zones",
            "cognitive schema", "cultural toolkit", "classification",
            "boundary object", "knowledge production", "sensemaking",
        ],
        "seed_terms": [
            "sociology of knowledge Mannheim",
            "social construction science technology",
            "cultural production field Bourdieu",
            "cognitive sociology DiMaggio",
        ],
        "canonical_works": [
            "Mannheim 1936 Ideology and Utopia",
            "Latour Woolgar 1979 Laboratory Life",
            "Knorr Cetina 1999 Epistemic Cultures",
        ],
    },
}


def get_perspective(name: str) -> dict | None:
    return PERSPECTIVES.get(name)


def list_perspectives() -> list[tuple[str, str]]:
    """Return list of (key, label) pairs."""
    return [(k, v["label"]) for k, v in PERSPECTIVES.items()]


def perspective_context(name: str) -> str:
    """Return a compact string for injection into Claude prompts."""
    p = PERSPECTIVES.get(name)
    if not p:
        return ""
    theorists = ", ".join(p["key_theorists"][:6])
    concepts = ", ".join(p["core_concepts"][:8])
    return (
        f"Theoretical perspective: {p['label']}\n"
        f"Key theorists: {theorists}\n"
        f"Core concepts: {concepts}\n"
        f"Focus: {p['description']}"
    )
