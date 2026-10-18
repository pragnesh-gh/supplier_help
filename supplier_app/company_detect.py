"""Find a real company name in a chat message. Deterministic, no model.

Used only to offer research ("Research Knorr-Bremse?"); it never starts a run by itself.
Ambiguity (which Knorr-Bremse?) is resolved later by the research identity step.
"""
import re

LEGAL_SUFFIX = (r"(?:AG|GmbH|SE|SA|S\.A\.|S\.p\.A\.|SpA|N\.V\.|NV|B\.V\.|BV|Ltd\.?|Limited|Inc\.?|LLC|PLC|plc|"
                r"Corp\.?|Corporation|Co\.?|KG|KGaA|AB|Oy|Oyj|A/S|ASA|Pty|Sdn Bhd|KK|S\.r\.l\.|Srl|SAS|Group|Holding)")
TRIGGER = re.compile(r"^\s*(?:please\s+)?(?:deep\s+research|research|investigate|due\s+diligence\s+(?:on|for)|"
                     r"check\s+out|look\s+into|look\s+up|tell\s+me\s+about|what\s+about|who\s+is|info\s+on|"
                     r"what\s+do\s+you\s+know\s+about|run\s+(?:a\s+)?(?:deep\s+)?research\s+on)\b[\s:,-]*", re.I)
EXPLICIT = re.compile(r"^\s*(?:please\s+)?(?:deep\s+research|research|investigate|due\s+diligence\s+(?:on|for)|"
                      r"check\s+out|look\s+into|run\s+(?:a\s+)?(?:deep\s+)?research\s+on)\b", re.I)
EXPLICIT_WORDS = ("research", "investigate", "web search", "latest news", "public sources", "due diligence")
# Words that mean the user is asking about the catalogue, not naming a company.
INTENT = {"compare", "comparison", "rank", "ranking", "lowest", "highest", "best", "worst", "count", "how many",
          "formula", "weight", "weights", "trend", "history", "overview", "summary", "summarise", "summarize",
          "explain", "why", "score", "scores", "scored", "risk", "risks", "supplier", "suppliers", "catalog",
          "catalogue", "dataset", "csv", "delivery", "financial", "quality", "volume", "these", "selected",
          "favorite", "favorites", "shortlist", "approval", "report", "strike", "fine", "recall", "gaps",
          "missing", "unknown", "strengths", "red flags", "flags", "coverage", "legal", "country", "people",
          "operations", "reputation", "safety"}
GENERIC = {"company", "companies", "supplier", "suppliers", "risk", "it", "them", "this", "that", "the company",
           "a company", "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "yes", "no", "help", "test",
           "the", "a", "an", "me", "us", "you", "ceo", "cfo", "cto", "esg", "csv", "iso", "kpi", "iris", "eu",
           "trends", "profile", "profiles", "data", "values", "it's", "its"}
STARTERS = {"what", "which", "who", "whom", "why", "how", "when", "where", "is", "are", "was", "were", "do", "does",
            "did", "can", "could", "should", "would", "will", "tell", "show", "give", "find", "list", "please",
            "compare", "rank", "explain", "i", "we", "my", "our", "the", "a", "an", "and", "or", "but", "any",
            "about", "for", "on", "of", "in", "with", "to", "from", "hi", "hello", "hey", "thanks", "ok", "yes", "no",
            "open", "read", "start", "stop", "go", "back", "more", "next", "new", "great", "good", "fine"}
TOKEN = r"[A-Z0-9][\w&.\-/']*"
CAP_RUN = re.compile(rf"(?<![\w&])({TOKEN}(?:\s+(?:&\s+)?{TOKEN})*(?:\s+{LEGAL_SUFFIX})?)")
SUFFIX_END = re.compile(rf"\b{LEGAL_SUFFIX}$")


def _clean(candidate):
    c = candidate.strip().strip("\"'“”‘’").strip()
    c = re.sub(r"[?!.,;:]+$", "", c).strip()
    c = re.sub(r"\s+(?:please|now|for me|risk|risks|supplier|company|again)$", "", c, flags=re.I).strip()
    words = c.split()
    while words and words[0].casefold() in STARTERS:
        words.pop(0)
    return " ".join(words)[:200]


def _rejected(candidate, known_names, columns):
    low = candidate.casefold()
    if not low or low in GENERIC or len(low) < 2 or len(candidate.split()) > 8:
        return True
    if re.search(r"(?<!\w)supp_\d{5}(?!\w)", low):
        return True
    if low in known_names or any(low == c.casefold() for c in columns):
        return True
    tokens = set(re.findall(r"[a-z]+", low))
    if any(" " in w and w in low for w in INTENT) or (tokens and tokens <= (INTENT | STARTERS | GENERIC)):
        return True
    return False


def detect(message, known_names=(), columns=()):
    """Return {"company", "confident"} for a company-like name in the message, else None."""
    if not isinstance(message, str):
        return None
    known = {n.casefold() for n in known_names}
    text = message.strip()
    body = TRIGGER.sub("", text, count=1).strip()
    candidates = []
    candidates += re.findall(r"[\"“']([^\"”']{2,80})[\"”']", text)
    m = re.search(r"\b(?:about|on|for|regarding|into|of)\s+([^?.!,;\n]{2,80})", body)
    if m and re.search(r"[A-Z]", m.group(1)):
        candidates.append(m.group(1))
    tokens = body.split()
    if body and (body != text or 1 <= len(tokens) <= 3) and len(tokens) <= 6 and "?" not in body:
        candidates.append(body)
    candidates += [g for g in CAP_RUN.findall(body)]
    for raw in candidates:
        name = _clean(raw)
        if _rejected(name, known, columns):
            continue
        caps = [w for w in name.split() if w[:1].isupper() or w[:1].isdigit()]
        suffix = bool(SUFFIX_END.search(name))
        only_name = re.sub(r"[?!.,;:]+$", "", body).strip().strip("\"'“”").casefold() == name.casefold()
        if not (suffix or caps or only_name):
            continue
        if not suffix and not caps and not only_name:
            continue
        if len(caps) == 1 and not suffix and not only_name and caps[0].casefold() in STARTERS:
            continue
        confident = suffix or len(caps) >= 2 or (only_name and bool(caps))
        return {"company": name, "confident": confident}
    return None


def explicit_request(message):
    """True when the user explicitly asks for research ("research X", "investigate X", ...)."""
    if not isinstance(message, str):
        return False
    return bool(EXPLICIT.search(message)) or any(w in message.casefold() for w in EXPLICIT_WORDS)


def starts_with_request(message):
    """True when the message starts with a research request ("research X", "investigate X")."""
    return isinstance(message, str) and bool(EXPLICIT.search(message))
