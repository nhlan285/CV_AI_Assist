import math
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlparse

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from recruitment.models import CVDocument, Skill


_TOKENIZER = None
_MODEL = None
_SPACY_NLP = None
_SPACY_MATCHER = None
_SPACY_MATCHER_SIGNATURE = None

SECTION_LABELS = {
    "skills": [
        "skills",
        "technical skills",
        "core skills",
        "ky nang",
        "ky nang chuyen mon",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "kinh nghiem",
        "kinh nghiem lam viec",
    ],
    "education": [
        "education",
        "hoc van",
        "dai hoc",
        "university",
        "academic",
    ],
    "projects": [
        "projects",
        "project",
        "du an",
        "portfolio",
    ],
    "certifications": [
        "certifications",
        "certification",
        "certificates",
        "chung chi",
        "certificate",
    ],
}

SECTION_ALIASES = None

SECTION_WEIGHTS = {
    "experience": 1.0,
    "projects": 0.95,
    "skills": 0.75,
    "certifications": 0.7,
    "education": 0.6,
    "other": 0.45,
}

REQUIREMENT_SOURCE_WEIGHTS = {
    "required_skills": 1.0,
    "requirements": 0.9,
    "description": 0.6,
}

REQUIREMENT_MATCH_THRESHOLD = 52

ATS_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "build",
    "can",
    "co",
    "collaborate",
    "develop",
    "do",
    "duoc",
    "for",
    "from",
    "have",
    "in",
    "is",
    "job",
    "lam",
    "mot",
    "must",
    "of",
    "or",
    "required",
    "should",
    "the",
    "to",
    "ung",
    "using",
    "va",
    "voi",
    "with",
    "work",
    "yeu",
}

DEFAULT_SKILL_ALIASES = {
    "Python": ["python"],
    "Django": ["django", "django framework"],
    "Django REST Framework": ["django rest framework", "drf"],
    "REST API": ["rest api", "restful api", "restful apis", "api rest"],
    "JavaScript": ["javascript", "js", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "React": ["react", "reactjs", "react js", "react.js"],
    "Vue.js": ["vue", "vuejs", "vue js", "vue.js"],
    "Node.js": ["node", "nodejs", "node js", "node.js"],
    "Express.js": ["express", "expressjs", "express js", "express.js"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "SQL": ["sql"],
    "SQLite": ["sqlite", "sqlite3"],
    "PostgreSQL": ["postgresql", "postgres", "postgre sql"],
    "MySQL": ["mysql", "my sql"],
    "MongoDB": ["mongodb", "mongo db"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Git": ["git", "github", "gitlab"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure", "microsoft azure"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "dl"],
    "NLP": ["nlp", "natural language processing", "xu ly ngon ngu tu nhien"],
    "spaCy": ["spacy", "spa cy"],
    "sentence-transformers": ["sentence transformers", "sentence-transformers", "sentence transformer"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy", "num py"],
    "Scikit-learn": ["scikit learn", "scikit-learn", "sklearn"],
    "TensorFlow": ["tensorflow", "tensor flow"],
    "PyTorch": ["pytorch", "py torch"],
    "C": ["c"],
    "C++": ["c++", "cpp", "cplusplus"],
    "C/C++": ["c/c++", "c c++", "c and c++", "c/cpp", "c++", "cpp", "cplusplus"],
    "C#": ["c#", "c sharp", "csharp"],
    "Java": ["java"],
    "PHP": ["php"],
    "Laravel": ["laravel"],
    "Ruby": ["ruby"],
    "Go": ["go", "golang"],
    "English": ["english", "tieng anh"],
    "Communication": ["communication", "giao tiep"],
    "Excel": ["excel", "microsoft excel"],
    "Research": ["research", "nghien cuu"],
}


SKILL_ALIASES = DEFAULT_SKILL_ALIASES
SKILL_ALIAS_MAP = None
SKILL_ALIAS_LOOKUP = None


def reset_skill_alias_cache():
    global SKILL_ALIAS_MAP, SKILL_ALIAS_LOOKUP, _SPACY_MATCHER, _SPACY_MATCHER_SIGNATURE
    SKILL_ALIAS_MAP = None
    SKILL_ALIAS_LOOKUP = None
    _SPACY_MATCHER = None
    _SPACY_MATCHER_SIGNATURE = None


def build_runtime_skill_aliases():
    alias_map = {
        canonical: set([canonical, *aliases])
        for canonical, aliases in DEFAULT_SKILL_ALIASES.items()
    }
    try:
        skills = Skill.objects.filter(is_active=True).prefetch_related("aliases")
        for skill in skills:
            aliases = alias_map.setdefault(skill.name, set())
            aliases.add(skill.name)
            for alias in skill.aliases.all():
                if alias.is_active:
                    aliases.add(alias.alias)
    except (OperationalError, ProgrammingError):
        pass
    return {
        canonical: sorted(aliases, key=lambda value: normalize_skill_phrase(value))
        for canonical, aliases in alias_map.items()
    }


def get_skill_aliases():
    global SKILL_ALIAS_MAP
    if SKILL_ALIAS_MAP is None:
        SKILL_ALIAS_MAP = build_runtime_skill_aliases()
    return SKILL_ALIAS_MAP


def build_skill_alias_lookup(alias_map=None):
    alias_map = alias_map or get_skill_aliases()
    lookup = {}
    for canonical, aliases in alias_map.items():
        for alias in [canonical, *aliases]:
            lookup[normalize_skill_phrase(alias)] = canonical
            lookup[compact_skill_phrase(alias)] = canonical
    return lookup


def get_skill_alias_lookup():
    global SKILL_ALIAS_LOOKUP
    if SKILL_ALIAS_LOOKUP is None:
        SKILL_ALIAS_LOOKUP = build_skill_alias_lookup()
    return SKILL_ALIAS_LOOKUP


def extract_pdf_text(file_path):
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Chua cai PyMuPDF. Hay chay: pip install -r requirements.txt") from exc

    text_parts = []
    with fitz.open(file_path) as document:
        for page in document:
            text_parts.append(page.get_text("text"))
    return "\n".join(part.strip() for part in text_parts if part.strip()).strip()


def ensure_cv_text(cv_document):
    if cv_document.extracted_text and cv_document.parse_status == CVDocument.ParseStatus.PARSED:
        if (
            not cv_document.extracted_skills
            and not cv_document.extracted_email
            and not cv_document.extracted_phone
        ) or not cv_document.skill_evidence or not cv_document.parsed_sections:
            populate_cv_parsed_fields(cv_document, cv_document.extracted_text)
        return cv_document.extracted_text

    try:
        extracted = extract_pdf_text(cv_document.file.path)
    except Exception as exc:
        cv_document.parse_status = CVDocument.ParseStatus.FAILED
        cv_document.parse_error = str(exc)
        cv_document.save(update_fields=["parse_status", "parse_error"])
        raise

    cv_document.extracted_text = extracted
    cv_document.parse_status = CVDocument.ParseStatus.PARSED if extracted else CVDocument.ParseStatus.FAILED
    cv_document.parse_error = "" if extracted else "Khong tim thay text trong PDF. MVP chua ho tro OCR file scan."
    populate_cv_parsed_fields(cv_document, extracted, save=False)
    cv_document.save(
        update_fields=[
            "extracted_text",
            "extracted_email",
            "extracted_phone",
            "extracted_links",
            "extracted_skills",
            "education_summary",
            "experience_summary",
            "project_summary",
            "certification_summary",
            "parsed_sections",
            "skill_evidence",
            "parse_status",
            "parse_error",
        ]
    )
    return extracted


def populate_cv_parsed_fields(cv_document, cv_text, save=True):
    parsed_profile = parse_cv_profile(cv_text)
    cv_document.extracted_email = parsed_profile["email"]
    cv_document.extracted_phone = parsed_profile["phone"]
    cv_document.extracted_links = parsed_profile["links"]
    cv_document.extracted_skills = ", ".join(parsed_profile["skills"])
    cv_document.education_summary = parsed_profile["education_summary"]
    cv_document.experience_summary = parsed_profile["experience_summary"]
    cv_document.project_summary = parsed_profile["project_summary"]
    cv_document.certification_summary = parsed_profile["certification_summary"]
    cv_document.parsed_sections = parsed_profile["sections"]
    cv_document.skill_evidence = parsed_profile["skill_evidence"]
    if save:
        cv_document.save(
            update_fields=[
                "extracted_email",
                "extracted_phone",
                "extracted_links",
                "extracted_skills",
                "education_summary",
                "experience_summary",
                "project_summary",
                "certification_summary",
                "parsed_sections",
                "skill_evidence",
            ]
        )


def calculate_application_ats(cv_text, job):
    job_text = build_job_text(job)
    semantic_score, note = semantic_similarity_score(cv_text, job_text)
    requirement_result = match_job_requirements(cv_text, job)
    matched = [item["label"] for item in requirement_result["matched_requirements"]]
    missing = [item["label"] for item in requirement_result["missing_requirements"]]
    skill_score = requirement_result["score"]
    legacy_skills = split_skills(job.required_skills)
    legacy_matched, legacy_missing, legacy_evidence = match_skills_with_evidence(cv_text, legacy_skills)
    experience_score = detect_experience_signal(cv_text)
    education_score = detect_education_signal(cv_text)
    domain_score = detect_domain_signal(cv_text, job_text)
    section_counts = Counter(item["section"] for item in requirement_result["evidence"])

    final_score = (
        skill_score * 0.45
        + semantic_score * 0.30
        + requirement_result["evidence_depth_score"] * 0.10
        + experience_score * 0.10
        + education_score * 0.05
    )
    final_score = round(max(0, min(100, final_score)), 2)
    breakdown = {
        "semantic_score": round(max(0, min(100, semantic_score)), 2),
        "skill_score": round(max(0, min(100, skill_score)), 2),
        "requirement_score": round(max(0, min(100, skill_score)), 2),
        "evidence_depth_score": round(requirement_result["evidence_depth_score"], 2),
        "experience_score": round(experience_score, 2),
        "education_score": round(education_score, 2),
        "domain_score": round(domain_score, 2),
        "requirements": requirement_result["requirements"],
        "requirement_matches": requirement_result["matched_requirements"][:20],
        "requirement_missing": requirement_result["missing_requirements"][:20],
        "requirement_evidence": requirement_result["evidence"][:20],
        "skill_evidence": legacy_evidence[:20],
        "legacy_matched_skills": legacy_matched,
        "legacy_missing_skills": legacy_missing,
        "section_skill_counts": dict(section_counts),
        "weights": {
            "requirements": 0.45,
            "semantic": 0.30,
            "evidence_depth": 0.10,
            "experience": 0.10,
            "education": 0.05,
        },
    }
    summary = generate_ai_summary(final_score, breakdown, matched, missing)

    return {
        "score": final_score,
        "semantic_score": breakdown["semantic_score"],
        "skill_score": breakdown["skill_score"],
        "breakdown": breakdown,
        "matched_skills": ", ".join(matched),
        "missing_skills": ", ".join(missing),
        "summary": summary,
        "notes": note,
    }


def build_job_text(job):
    return "\n".join(
        [
            job.title,
            job.company.name,
            job.location,
            job.required_skills,
            job.description,
            job.requirements,
            job.benefits,
        ]
    )


def extract_job_requirements(job):
    requirements = []

    for phrase in split_requirement_phrases(job.required_skills):
        add_requirement(requirements, phrase, "required_skills", "skill")

    for statement in split_text_statements(job.requirements):
        add_requirement(requirements, statement, "requirements", "requirement")

    if len(requirements) < 8:
        for statement in split_text_statements(job.description):
            add_requirement(requirements, statement, "description", "responsibility")
            if len(requirements) >= 12:
                break

    return requirements[:16]


def add_requirement(requirements, text, source, kind):
    cleaned = clean_requirement_text(text)
    if not cleaned:
        return
    key = compact_skill_phrase(cleaned)
    if not key or any(item["key"] == key for item in requirements):
        return
    requirements.append(
        {
            "key": key,
            "label": requirement_label(cleaned),
            "text": cleaned,
            "source": source,
            "kind": kind,
            "weight": REQUIREMENT_SOURCE_WEIGHTS.get(source, 0.6),
        }
    )


def split_requirement_phrases(raw_text):
    parts = re.split(r"[,;\n|]+|\s+/\s+|â€¢|•", raw_text or "")
    return [part for part in (clean_requirement_text(part) for part in parts) if part]


def split_text_statements(raw_text):
    statements = []
    for raw_line in (raw_text or "").splitlines():
        line = clean_requirement_text(raw_line)
        if not line:
            continue
        chunks = re.split(r"(?<=[.!?])\s+|[;•]+|â€¢+", line)
        for chunk in chunks:
            cleaned = clean_requirement_text(chunk)
            if is_useful_statement(cleaned):
                statements.append(cleaned)
    return dedupe_text_items(statements)


def clean_requirement_text(text):
    cleaned = re.sub(r"^\s*(?:[-*+•]|\d+[\).:-])\s*", "", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned.strip(" \t\r\n-–—:;,."))
    return cleaned[:280]


def is_useful_statement(text):
    if not text:
        return False
    tokens = semantic_tokens(text)
    if len(tokens) >= 2:
        return True
    return len(text.strip()) >= 2 and any(char.isupper() for char in text)


def requirement_label(text):
    cleaned = clean_requirement_text(text)
    if len(cleaned) <= 90:
        return cleaned
    return cleaned[:87].rstrip() + "..."


def extract_cv_evidence_units(cv_text):
    sections = split_cv_sections(cv_text)
    evidence_units = []
    for section in sections:
        section_name = section["name"]
        section_text = section["text"]
        if section_name == "skills":
            for term in split_requirement_phrases(section_text):
                add_evidence_unit(evidence_units, term, section_name)
        for statement in split_text_statements(section_text):
            add_evidence_unit(evidence_units, statement, section_name)

    if not evidence_units:
        for statement in split_text_statements(cv_text):
            add_evidence_unit(evidence_units, statement, "other")

    return evidence_units[:80]


def add_evidence_unit(evidence_units, text, section):
    cleaned = clean_requirement_text(text)
    if not cleaned:
        return
    key = (section, normalize_skill_phrase(cleaned)[:160])
    if any(item["key"] == key for item in evidence_units):
        return
    evidence_units.append(
        {
            "key": key,
            "text": cleaned,
            "section": section,
            "weight": SECTION_WEIGHTS.get(section, SECTION_WEIGHTS["other"]),
        }
    )


def match_job_requirements(cv_text, job):
    requirements = extract_job_requirements(job)
    evidence_units = extract_cv_evidence_units(cv_text)
    if not requirements:
        return {
            "score": 0,
            "evidence_depth_score": 0,
            "requirements": [],
            "matched_requirements": [],
            "missing_requirements": [],
            "evidence": [],
        }

    matched_requirements = []
    missing_requirements = []
    evidence = []
    total_weight = 0
    weighted_score = 0

    for requirement in requirements:
        best = best_requirement_evidence(requirement, evidence_units)
        total_weight += requirement["weight"]
        weighted_score += requirement["weight"] * best["score"]

        result = {
            "label": requirement["label"],
            "text": requirement["text"],
            "source": requirement["source"],
            "kind": requirement["kind"],
            "score": round(best["score"], 2),
        }
        if best["score"] >= REQUIREMENT_MATCH_THRESHOLD:
            result.update(
                {
                    "section": best["section"],
                    "evidence": best["evidence"],
                }
            )
            matched_requirements.append(result)
            evidence.append(result)
        else:
            missing_requirements.append(result)

    return {
        "score": weighted_score / total_weight if total_weight else 0,
        "evidence_depth_score": evidence_depth_score(evidence),
        "requirements": [
            {
                "label": item["label"],
                "text": item["text"],
                "source": item["source"],
                "kind": item["kind"],
                "weight": item["weight"],
            }
            for item in requirements
        ],
        "matched_requirements": matched_requirements,
        "missing_requirements": missing_requirements,
        "evidence": dedupe_requirement_evidence(evidence),
    }


def best_requirement_evidence(requirement, evidence_units):
    best = {"score": 0, "section": "other", "evidence": ""}
    for unit in evidence_units:
        raw_score = semantic_text_match_score(requirement["text"], unit["text"])
        section_bonus = 0.92 + (unit["weight"] * 0.12)
        score = min(100, raw_score * section_bonus)
        if score > best["score"]:
            best = {
                "score": score,
                "section": unit["section"],
                "evidence": unit["text"],
            }
    return best


def semantic_text_match_score(text_a, text_b):
    normalized_a = normalize_skill_phrase(text_a)
    normalized_b = normalize_skill_phrase(text_b)
    if not normalized_a or not normalized_b:
        return 0
    if phrase_in_text(normalized_a, normalized_b) or phrase_in_text(normalized_b, normalized_a):
        return 96

    tokens_a = semantic_tokens(text_a)
    tokens_b = semantic_tokens(text_b)
    if not tokens_a or not tokens_b:
        return SequenceMatcher(None, normalized_a, normalized_b).ratio() * 35

    unique_a = set(tokens_a)
    unique_b = set(tokens_b)
    if len(unique_a) <= 4 and unique_a.issubset(unique_b):
        return 92
    if len(unique_b) <= 4 and unique_b.issubset(unique_a):
        return 88

    token_score = token_cosine_similarity(tokens_a, tokens_b)
    containment_score = token_containment_score(tokens_a, tokens_b)
    ngram_score = char_ngram_jaccard(normalized_a, normalized_b)
    sequence_score = SequenceMatcher(None, normalized_a, normalized_b).ratio()

    return (
        token_score * 40
        + containment_score * 35
        + ngram_score * 15
        + sequence_score * 10
    )


def semantic_tokens(text):
    tokens = []
    for token in re.findall(r"[a-z0-9+#.]+", normalize_skill_phrase(text)):
        token = token.strip(".")
        token = normalize_semantic_token(token)
        if len(token) <= 1 or token in ATS_STOP_WORDS:
            continue
        tokens.append(token)
    return tokens


def normalize_semantic_token(token):
    if token == "restful":
        return "rest"
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
        return token[:-1]
    return token


def token_cosine_similarity(tokens_a, tokens_b):
    counts_a = Counter(tokens_a)
    counts_b = Counter(tokens_b)
    shared = set(counts_a) & set(counts_b)
    numerator = sum(counts_a[token] * counts_b[token] for token in shared)
    denominator = math.sqrt(sum(v * v for v in counts_a.values())) * math.sqrt(
        sum(v * v for v in counts_b.values())
    )
    return numerator / denominator if denominator else 0


def token_containment_score(tokens_a, tokens_b):
    unique_a = set(tokens_a)
    unique_b = set(tokens_b)
    if not unique_a or not unique_b:
        return 0
    return len(unique_a & unique_b) / max(1, min(len(unique_a), len(unique_b)))


def char_ngram_jaccard(text_a, text_b, size=3):
    grams_a = char_ngrams(text_a, size)
    grams_b = char_ngrams(text_b, size)
    if not grams_a or not grams_b:
        return 0
    return len(grams_a & grams_b) / len(grams_a | grams_b)


def char_ngrams(text, size):
    compact = compact_skill_phrase(text)
    if len(compact) <= size:
        return {compact} if compact else set()
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def evidence_depth_score(evidence):
    if not evidence:
        return 0
    sections = {item.get("section", "other") for item in evidence}
    section_score = min(100, len(sections) * 28)
    strong_evidence = sum(
        1
        for item in evidence
        if item.get("section") in {"experience", "projects", "certifications"}
    )
    strong_score = min(100, strong_evidence * 18)
    return min(100, section_score * 0.45 + strong_score * 0.55)


def dedupe_requirement_evidence(items):
    result = []
    seen = set()
    for item in items:
        key = (
            compact_skill_phrase(item.get("label", "")),
            item.get("section", "other"),
            normalize_skill_phrase(item.get("evidence", ""))[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def dedupe_text_items(items):
    result = []
    seen = set()
    for item in items:
        key = compact_skill_phrase(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def split_skills(raw_text):
    if not raw_text:
        return []
    parts = re.split(r"[,;\n|•]+|\s+/\s+", raw_text)
    skills = []
    seen = set()
    for part in parts:
        skill = canonicalize_skill(part)
        if not skill:
            continue
        key = compact_skill_phrase(skill)
        if key in seen:
            continue
        seen.add(key)
        skills.append(skill)
    return skills


def detect_known_skills(text):
    evidence = detect_skill_evidence(text)
    if evidence:
        return dedupe_preserve_order(item["skill"] for item in evidence)

    normalized_text = normalize_skill_phrase(text)
    detected = []
    for skill in get_skill_aliases():
        if skill_in_text(skill, normalized_text):
            detected.append(skill)
    return dedupe_preserve_order(detected)


def match_skills(cv_text, required_skills):
    normalized_cv = normalize_skill_phrase(cv_text)
    matched = []
    missing = []
    for skill in required_skills:
        canonical_skill = canonicalize_skill(skill)
        if not canonical_skill:
            continue
        if skill_in_text(canonical_skill, normalized_cv):
            matched.append(canonical_skill)
        else:
            missing.append(canonical_skill)
    return dedupe_preserve_order(matched), dedupe_preserve_order(missing)


def match_skills_with_evidence(cv_text, required_skills):
    all_evidence = detect_skill_evidence(cv_text)
    evidence_by_skill = {}
    for evidence in all_evidence:
        evidence_by_skill.setdefault(evidence["skill"], []).append(evidence)

    matched = []
    missing = []
    matched_evidence = []
    normalized_cv = normalize_skill_phrase(cv_text)
    for skill in required_skills:
        canonical_skill = canonicalize_skill(skill)
        if not canonical_skill:
            continue
        if canonical_skill in evidence_by_skill:
            matched.append(canonical_skill)
            matched_evidence.extend(evidence_by_skill[canonical_skill][:3])
        elif skill_in_text(canonical_skill, normalized_cv):
            matched.append(canonical_skill)
            matched_evidence.append(
                {
                    "skill": canonical_skill,
                    "alias": canonical_skill,
                    "section": "other",
                    "sentence": evidence_sentence(cv_text, canonical_skill),
                    "start": -1,
                    "end": -1,
                }
            )
        else:
            missing.append(canonical_skill)
    return (
        dedupe_preserve_order(matched),
        dedupe_preserve_order(missing),
        dedupe_skill_evidence(matched_evidence),
    )


def contextual_skill_score(required_skills, matched_skills, matched_evidence):
    if not required_skills:
        return 0
    evidence_by_skill = {}
    for evidence in matched_evidence:
        evidence_by_skill.setdefault(evidence["skill"], []).append(evidence)

    score = 0
    for skill in dedupe_preserve_order(canonicalize_skill(value) for value in required_skills):
        if skill not in matched_skills:
            continue
        best_weight = max(
            (SECTION_WEIGHTS.get(item["section"], SECTION_WEIGHTS["other"]) for item in evidence_by_skill.get(skill, [])),
            default=SECTION_WEIGHTS["other"],
        )
        score += best_weight * 100
    return min(100, score / len(required_skills))


def detect_skill_evidence(text):
    try:
        return detect_skill_evidence_with_spacy(text)
    except Exception:
        return detect_skill_evidence_with_rules(text)


def detect_skill_evidence_with_spacy(text):
    if not text:
        return []
    nlp, matcher = get_spacy_matcher()
    doc = nlp(text)
    sections = split_cv_sections(text)
    evidence = []
    for match_id, start, end in matcher(doc):
        skill_name = nlp.vocab.strings[match_id]
        span = doc[start:end]
        evidence.append(
            {
                "skill": skill_name,
                "alias": span.text,
                "section": section_for_offset(sections, span.start_char),
                "sentence": sentence_for_span(doc, span),
                "start": span.start_char,
                "end": span.end_char,
            }
        )
    return dedupe_skill_evidence(evidence)


def detect_skill_evidence_with_rules(text):
    normalized_text = normalize_skill_phrase(text)
    sections = split_cv_sections(text)
    evidence = []
    for skill in get_skill_aliases():
        aliases = get_skill_aliases().get(skill, [])
        for candidate in [skill, *aliases]:
            normalized_candidate = normalize_skill_phrase(candidate)
            match = re.search(
                r"(?<![\w+#])" + re.escape(normalized_candidate) + r"(?![\w+#])",
                normalized_text,
            )
            if not match:
                continue
            original_sentence = evidence_sentence(text, candidate)
            evidence.append(
                {
                    "skill": skill,
                    "alias": candidate,
                    "section": section_for_sentence(sections, original_sentence),
                    "sentence": original_sentence,
                    "start": -1,
                    "end": -1,
                }
            )
            break
    return dedupe_skill_evidence(evidence)


def get_spacy_matcher():
    global _SPACY_NLP, _SPACY_MATCHER, _SPACY_MATCHER_SIGNATURE
    alias_map = get_skill_aliases()
    signature = tuple(
        (skill, tuple(sorted(aliases, key=normalize_skill_phrase)))
        for skill, aliases in sorted(alias_map.items())
    )
    if _SPACY_NLP is not None and _SPACY_MATCHER is not None and _SPACY_MATCHER_SIGNATURE == signature:
        return _SPACY_NLP, _SPACY_MATCHER

    try:
        import spacy
        from spacy.matcher import PhraseMatcher
    except ImportError as exc:
        raise RuntimeError("Chua cai spaCy. Hay chay: pip install -r requirements.txt") from exc

    nlp = spacy.blank("xx")
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    for skill, aliases in alias_map.items():
        patterns = [nlp.make_doc(alias) for alias in [skill, *aliases] if alias]
        if patterns:
            matcher.add(skill, patterns)

    _SPACY_NLP = nlp
    _SPACY_MATCHER = matcher
    _SPACY_MATCHER_SIGNATURE = signature
    return _SPACY_NLP, _SPACY_MATCHER


def split_cv_sections(text):
    lines = (text or "").splitlines()
    sections = []
    current_section = "other"
    current_start = 0
    current_lines = []
    cursor = 0
    section_aliases = get_section_aliases()

    for line in lines:
        raw_line = line.rstrip()
        next_cursor = cursor + len(line) + 1
        detected_section, inline_text = detect_section_heading(raw_line, section_aliases)
        if detected_section:
            if current_lines:
                sections.append(
                    {
                        "name": current_section,
                        "start": current_start,
                        "end": cursor,
                        "text": "\n".join(current_lines).strip(),
                    }
                )
            current_section = detected_section
            current_start = cursor + raw_line.find(inline_text) if inline_text else next_cursor
            current_lines = [inline_text] if inline_text else []
        else:
            current_lines.append(raw_line)
        cursor = next_cursor

    if current_lines or not sections:
        sections.append(
            {
                "name": current_section,
                "start": current_start,
                "end": len(text or ""),
                "text": "\n".join(current_lines).strip(),
            }
        )
    return [section for section in sections if section["text"] or section["name"] != "other"]


def detect_section_heading(raw_line, section_aliases):
    normalized = normalize_skill_phrase(raw_line.strip(":-"))
    detected_section = section_aliases.get(normalized)
    if detected_section:
        return detected_section, ""

    match = re.match(r"^\s*([^:]{2,40})\s*:\s*(.+)$", raw_line or "")
    if not match:
        return None, ""
    heading = normalize_skill_phrase(match.group(1))
    detected_section = section_aliases.get(heading)
    if detected_section:
        return detected_section, match.group(2).strip()
    return None, ""


def get_section_aliases():
    global SECTION_ALIASES
    if SECTION_ALIASES is None:
        SECTION_ALIASES = {
            normalize_skill_phrase(alias): section
            for section, aliases in SECTION_LABELS.items()
            for alias in aliases
        }
    return SECTION_ALIASES


def section_for_offset(sections, offset):
    for section in sections:
        if section["start"] <= offset <= section["end"]:
            return section["name"]
    return "other"


def section_for_sentence(sections, sentence):
    normalized_sentence = normalize_skill_phrase(sentence)
    for section in sections:
        if normalized_sentence and normalized_sentence in normalize_skill_phrase(section["text"]):
            return section["name"]
    return "other"


def sentence_for_span(doc, span):
    text = doc.text
    start = text.rfind("\n", 0, span.start_char)
    end = text.find("\n", span.end_char)
    if end == -1:
        end = len(text)
    return text[start + 1 : end].strip()[:260]


def evidence_sentence(text, phrase):
    normalized_phrase = normalize_skill_phrase(phrase)
    for line in (text or "").splitlines():
        if normalized_phrase in normalize_skill_phrase(line):
            return line.strip()[:260]
    return ""


def dedupe_skill_evidence(items):
    result = []
    seen = set()
    for item in items:
        key = (
            compact_skill_phrase(item.get("skill", "")),
            item.get("section", "other"),
            normalize_skill_phrase(item.get("sentence", ""))[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def canonicalize_skill(skill):
    cleaned = clean_skill_label(skill)
    if not cleaned:
        return ""
    lookup = get_skill_alias_lookup()
    return (
        lookup.get(normalize_skill_phrase(cleaned))
        or lookup.get(compact_skill_phrase(cleaned))
        or cleaned
    )


def clean_skill_label(skill):
    return re.sub(r"\s+", " ", (skill or "").strip(" \t\r\n-–—:")).strip()


def skill_in_text(skill, normalized_cv):
    aliases = get_skill_aliases().get(skill, [])
    candidates = [skill, *aliases]
    for candidate in candidates:
        normalized_candidate = normalize_skill_phrase(candidate)
        if phrase_in_text(normalized_candidate, normalized_cv):
            return True
    return False


def phrase_in_text(phrase, text):
    if not phrase:
        return False
    pattern = r"(?<![\w+#])" + re.escape(phrase) + r"(?![\w+#])"
    return re.search(pattern, text) is not None


def normalize_skill_phrase(text):
    normalized = normalize(text)
    normalized = re.sub(r"[._-]+", " ", normalized)
    normalized = re.sub(r"[(){}\[\],;:|•]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def compact_skill_phrase(text):
    return re.sub(r"[^a-z0-9+#]+", "", normalize_skill_phrase(text))


def dedupe_preserve_order(items):
    result = []
    seen = set()
    for item in items:
        key = compact_skill_phrase(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def semantic_similarity_score(cv_text, job_text):
    try:
        embeddings = encode_texts([cv_text, job_text])
        score = dot_product(embeddings[0], embeddings[1]) * 100
        return score, f"Semantic matching bang multilingual model {model_identifier()}."
    except Exception as exc:
        score = fallback_keyword_similarity(cv_text, job_text) * 100
        note = "Fallback keyword similarity vi semantic model chua san sang: " + str(exc)
        return score, note[:500]


def detect_experience_signal(text):
    normalized_text = normalize_skill_phrase(text)
    year_matches = re.findall(r"(\d{1,2})\s*(?:\+?\s*)?(?:nam|year|years)\s+(?:kinh nghiem|experience)", normalized_text)
    if year_matches:
        max_years = max(int(value) for value in year_matches)
        return min(100, 35 + max_years * 15)
    if any(keyword in normalized_text for keyword in ["kinh nghiem", "experience", "worked", "phat trien", "developed"]):
        return 55
    return 20


def detect_education_signal(text):
    normalized_text = normalize_skill_phrase(text)
    if any(keyword in normalized_text for keyword in ["dai hoc", "university", "bachelor", "engineer", "computer science"]):
        return 85
    if any(keyword in normalized_text for keyword in ["education", "hoc van", "degree", "certification", "certificate"]):
        return 65
    return 25


def detect_domain_signal(cv_text, job_text):
    cv_tokens = set(tokenize(cv_text))
    job_tokens = set(tokenize(job_text))
    if not cv_tokens or not job_tokens:
        return 0
    shared = cv_tokens & job_tokens
    return min(100, (len(shared) / max(1, len(job_tokens))) * 180)


def generate_ai_summary(final_score, breakdown, matched, missing):
    if final_score >= 85:
        fit_label = "Ứng viên phù hợp cao với yêu cầu tuyển dụng."
    elif final_score >= 70:
        fit_label = "Ứng viên có mức phù hợp tốt, nên được xem kỹ."
    elif final_score >= 50:
        fit_label = "Ứng viên phù hợp trung bình, cần recruiter đánh giá thêm."
    else:
        fit_label = "Ứng viên đang thiếu nhiều tín hiệu phù hợp so với JD."

    requirement_line = ""
    if matched:
        requirement_line = "Yêu cầu đã có bằng chứng: " + ", ".join(matched[:5]) + "."
    if missing:
        missing_line = "Yêu cầu còn thiếu hoặc chưa rõ: " + ", ".join(missing[:5]) + "."
    else:
        missing_line = "Không phát hiện yêu cầu chính nào bị thiếu."

    evidence_sections = breakdown.get("section_skill_counts", {})
    evidence_line = ""
    if evidence_sections:
        strong_sections = [
            section for section in ["experience", "projects"] if evidence_sections.get(section)
        ]
        if strong_sections:
            evidence_line = "Bằng chứng mạnh nằm trong " + ", ".join(strong_sections) + "."

    signal_line = (
        f"Semantic {breakdown['semantic_score']:.1f}, "
        f"requirement {breakdown['skill_score']:.1f}, "
        f"kinh nghiệm {breakdown['experience_score']:.1f}."
    )
    return " ".join(
        part for part in [fit_label, requirement_line, missing_line, evidence_line, signal_line] if part
    )


def parse_cv_profile(cv_text):
    text = cv_text or ""
    links = extract_links(text)
    sections = split_cv_sections(text)
    section_map = {section["name"]: section["text"] for section in sections if section["text"]}
    skill_evidence = detect_skill_evidence(text)
    section_skill_terms = extract_skill_section_terms(sections)
    return {
        "email": extract_email(text),
        "phone": extract_phone(text),
        "links": links,
        "skills": dedupe_preserve_order(
            [*section_skill_terms, *(item["skill"] for item in skill_evidence)]
        )
        or detect_known_skills(text),
        "education_summary": summarize_section(section_map.get("education"))
        or summarize_section_signal(text, ["education", "hoc van", "dai hoc", "university", "bachelor"]),
        "experience_summary": summarize_section(section_map.get("experience"))
        or summarize_section_signal(text, ["experience", "kinh nghiem", "worked", "developed"]),
        "project_summary": summarize_section(section_map.get("projects"))
        or summarize_section_signal(text, ["project", "du an", "portfolio", "github"]),
        "certification_summary": summarize_section(section_map.get("certifications"))
        or summarize_section_signal(text, ["certification", "certificate", "chung chi"]),
        "sections": serialize_sections(sections),
        "skill_evidence": skill_evidence[:40],
    }


def extract_skill_section_terms(sections):
    terms = []
    for section in sections:
        if section["name"] != "skills":
            continue
        for phrase in split_requirement_phrases(section["text"]):
            if is_reasonable_skill_term(phrase):
                terms.append(canonicalize_skill(phrase))
    return dedupe_preserve_order(terms)


def is_reasonable_skill_term(text):
    tokens = semantic_tokens(text)
    if not tokens:
        return False
    return len(tokens) <= 6 and len(text) <= 80


def extract_email(text):
    match = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text or "")
    return match.group(0) if match else ""


def extract_phone(text):
    phone_pattern = r"(?:\+?84|0)(?:[\s.-]?\d){8,10}"
    match = re.search(phone_pattern, text or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(0)).strip()


def extract_links(text):
    raw_links = re.findall(r"https?://[^\s)>\]]+|(?:github|linkedin)\.com/[^\s)>\]]+", text or "", flags=re.IGNORECASE)
    links = []
    seen = set()
    for raw_link in raw_links:
        link = raw_link.rstrip(".,;")
        if not link.startswith("http"):
            link = "https://" + link
        parsed = urlparse(link)
        if not parsed.netloc:
            continue
        key = link.casefold()
        if key in seen:
            continue
        seen.add(key)
        links.append(link)
    return links[:8]


def summarize_section_signal(text, keywords):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    normalized_keywords = [normalize_skill_phrase(keyword) for keyword in keywords]
    snippets = []
    for index, line in enumerate(lines):
        normalized_line = normalize_skill_phrase(line)
        if any(keyword in normalized_line for keyword in normalized_keywords):
            window = lines[index : index + 3]
            snippets.append(" / ".join(window))
    return "\n".join(snippets[:2])[:700]


def summarize_section(section_text):
    lines = [line.strip(" -•\t") for line in (section_text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[:4])[:700]


def serialize_sections(sections):
    return {
        section["name"]: summarize_section(section["text"])
        for section in sections
        if section["text"]
    }


def encode_texts(texts):
    tokenizer, model = get_transformer_model()
    import torch

    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )
    with torch.no_grad():
        output = model(**encoded)
    embeddings = mean_pool(output.last_hidden_state, encoded["attention_mask"])
    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
    return embeddings.cpu().tolist()


def get_transformer_model():
    global _TOKENIZER, _MODEL
    if _TOKENIZER is None or _MODEL is None:
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Chua cai transformers. Hay chay: pip install -r requirements.txt") from exc
        model_id = model_identifier()
        _TOKENIZER = AutoTokenizer.from_pretrained(model_id)
        _MODEL = AutoModel.from_pretrained(model_id)
        _MODEL.eval()
    return _TOKENIZER, _MODEL


def model_identifier():
    model_name = settings.ATS_EMBEDDING_MODEL
    if "/" in model_name:
        return model_name
    return f"sentence-transformers/{model_name}"


def mean_pool(token_embeddings, attention_mask):
    import torch

    mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    summed = torch.sum(token_embeddings * mask, 1)
    counts = torch.clamp(mask.sum(1), min=1e-9)
    return summed / counts


def dot_product(vector_a, vector_b):
    return float(sum(float(a) * float(b) for a, b in zip(vector_a, vector_b)))


def fallback_keyword_similarity(text_a, text_b):
    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0
    counts_a = Counter(tokens_a)
    counts_b = Counter(tokens_b)
    shared = set(counts_a) & set(counts_b)
    numerator = sum(counts_a[token] * counts_b[token] for token in shared)
    denominator = math.sqrt(sum(v * v for v in counts_a.values())) * math.sqrt(
        sum(v * v for v in counts_b.values())
    )
    return numerator / denominator if denominator else 0


def tokenize(text):
    return re.findall(r"\w+", normalize(text))


def normalize(text):
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return value.casefold()
