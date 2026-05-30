import math
import re
from collections import Counter

from django.conf import settings

from recruitment.models import CVDocument


_TOKENIZER = None
_MODEL = None


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
    cv_document.save(update_fields=["extracted_text", "parse_status", "parse_error"])
    return extracted


def calculate_application_ats(cv_text, job):
    job_text = build_job_text(job)
    semantic_score, note = semantic_similarity_score(cv_text, job_text)
    skills = split_skills(job.required_skills)
    matched, missing = match_skills(cv_text, skills)

    if skills:
        skill_score = (len(matched) / len(skills)) * 100
        final_score = (semantic_score * 0.85) + (skill_score * 0.15)
    else:
        final_score = semantic_score

    return {
        "score": round(max(0, min(100, final_score)), 2),
        "matched_skills": ", ".join(matched),
        "missing_skills": ", ".join(missing),
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


def split_skills(raw_text):
    if not raw_text:
        return []
    parts = re.split(r"[,;\n|/]+", raw_text)
    return [part.strip() for part in parts if part.strip()]


def match_skills(cv_text, required_skills):
    normalized_cv = normalize(cv_text)
    matched = []
    missing = []
    for skill in required_skills:
        if normalize(skill) in normalized_cv:
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing


def semantic_similarity_score(cv_text, job_text):
    try:
        embeddings = encode_texts([cv_text, job_text])
        score = dot_product(embeddings[0], embeddings[1]) * 100
        return score, f"Semantic matching bang multilingual model {model_identifier()}."
    except Exception as exc:
        score = fallback_keyword_similarity(cv_text, job_text) * 100
        note = "Fallback keyword similarity vi semantic model chua san sang: " + str(exc)
        return score, note[:500]


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
    return (text or "").casefold()
