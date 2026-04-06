import os
import csv
import re
import hmac
import hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter

from docx import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IN_CSV = PROJECT_ROOT / "file_index.csv"
OUT_CSV = PROJECT_ROOT / "file_index_with_dates.csv"

PROGRESS_EVERY = 200

MIN_YEAR = 2019
MAX_YEAR = 2026

TWO_DIGIT_YEAR_CUTOFF = 80  # 00..79 => 20xx, 80..99 => 19xx
PATIENT_SECRET_ENV = "PATIENT_ID_SECRET"


FIO_RE = re.compile(
    r"(?:Ф\.?\s*И\.?\s*О\.?|ФИО\s*пациента|ФИО|Фамилия\s*Имя\s*Отчество|Пациент(?:ка)?)\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)

DOB_RE = re.compile(
    r"(?:Дата\s*рождения|Число\s*,\s*месяц\s*,\s*год\s*рождения)\s*[:\-]\s*"
    r"([0-3]?\d[.\-/][01]?\d[.\-/]\d{4})\s*(?:г\.?\s*р\.?|гр\.?)?",
    re.IGNORECASE,
)

DOB_GR_RE = re.compile(
    r"\b([0-3]?\d[.\-/][01]?\d[.\-/]\d{4})\s*(?:г\.?\s*р\.?|гр\.?)\b",
    re.IGNORECASE,
)

MULTISPACE_RE = re.compile(r"\s+")
NON_LETTER_RE = re.compile(r"[^a-zа-яё-]+", re.IGNORECASE)

FILENAME_STOPWORDS = (
    "перв", "первич", "повт", "повтор", "узи", "онк", "шабл", "шаблон",
    "прием", "приём", "протокол", "копия", "копия", "new", "новый",
)

def normalize_name(raw_fio: str) -> str:
    s = (raw_fio or "").strip().lower().replace("ё", "е")
    s = s.replace(",", " ").replace(".", " ").replace(";", " ").replace(":", " ")
    s = MULTISPACE_RE.sub(" ", s).strip()
    if not s:
        return ""
    parts = [p for p in s.split(" ") if p]
    cleaned = []
    for p in parts:
        p2 = NON_LETTER_RE.sub("", p).strip("-")
        if p2:
            cleaned.append(p2)
    return " ".join(cleaned).strip()


def normalize_dob(raw_dob: str) -> str:
    s = (raw_dob or "").strip().lower()
    s = s.replace("г.р.", "").replace("г.р", "").replace("гр.", "").replace("гр", "").strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        try:
            return datetime.strptime(f"{d:02d}.{mo:02d}.{y}", "%d.%m.%Y").strftime("%Y-%m-%d")
        except ValueError:
            return ""
    return ""


def dob_to_birth_year(raw_dob: str) -> str:
    """Extract just the birth year from raw DOB string. Returns '' if can't parse."""
    iso = normalize_dob(raw_dob)
    if iso and len(iso) >= 4:
        year = iso[:4]
        # sanity check: patients born between 1920 and 2010
        try:
            y = int(year)
            if 1920 <= y <= 2010:
                return year
        except ValueError:
            pass
    return ""


def fio_from_filename(path: Path) -> str:
    stem = path.stem
    s = stem.replace("ё", "е")
    s = re.sub(r"[,_()]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""
    tokens = s.split(" ")
    cleaned = []
    for t in tokens:
        tl = t.lower().strip(".-")
        if not tl:
            continue
        if any(sw in tl for sw in FILENAME_STOPWORDS):
            continue
        cleaned.append(t.strip(".-"))
    if len(cleaned) < 2:
        return ""
    surname = cleaned[0]
    t1 = cleaned[1]
    t1_letters = re.sub(r"[^A-Za-zА-Яа-я]", "", t1)
    if t1_letters and len(t1_letters) <= 3 and t1_letters.isalpha():
        initials = t1_letters.upper()
        return f"{surname} {initials}"
    name = cleaned[1] if len(cleaned) >= 2 else ""
    patron = cleaned[2] if len(cleaned) >= 3 else ""
    if not name:
        return ""
    ini1 = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", name)[:1]
    ini2 = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", patron)[:1] if patron else ""
    if not ini1:
        return ""
    initials = (ini1 + ini2).upper()
    return f"{surname} {initials}"


def extract_fio_and_dob(text: str, path: Path) -> tuple[str, str, str]:
    fio = ""
    dob = ""
    m1 = FIO_RE.search(text)
    if m1:
        fio = m1.group(1).strip()
    m2 = DOB_RE.search(text)
    if m2:
        dob = m2.group(1).strip()
    if fio and not dob:
        m3 = DOB_GR_RE.search(text)
        if m3:
            dob = m3.group(1).strip()
    if fio and dob:
        return fio, dob, "docx"
    fio_fn = fio_from_filename(path)
    if fio_fn and dob:
        return fio_fn, dob, "filename"
    return "", "", "none"


def hmac_hex(secret: str, msg: str, length: int = 24) -> str:
    digest = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:length]


def make_patient_id(fio_raw: str, dob_raw: str) -> str:
    secret = os.getenv(PATIENT_SECRET_ENV)
    if not secret:
        raise RuntimeError(
            f"Missing env var {PATIENT_SECRET_ENV}. Example:\n"
            f'  export {PATIENT_SECRET_ENV}="..."\n'
            f"Do NOT hardcode the secret in the code."
        )
    fio_norm = normalize_name(fio_raw)
    dob_iso = normalize_dob(dob_raw)
    if not fio_norm or not dob_iso:
        return ""
    key = f"v1|{fio_norm}|{dob_iso}"
    return hmac_hex(secret, key, length=24)


def make_file_id(path: Path) -> str:
    secret = os.getenv(PATIENT_SECRET_ENV)
    if not secret:
        raise RuntimeError(f"Missing env var {PATIENT_SECRET_ENV}")
    try:
        rel = str(path.relative_to(PROJECT_ROOT))
    except Exception:
        rel = str(path)
    return hmac_hex(secret, f"file|v1|{rel}", length=16)


# ─────────────────────────────────────────────
# Date extraction (original, unchanged)
# ─────────────────────────────────────────────
DATE_DOT_YYYY_RE = re.compile(r"\b(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})\b")
DATE_SLASH_YYYY_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
DATE_DOT_YY_RE = re.compile(r"\b(\d{1,2})[.\-](\d{1,2})[.\-](\d{2})\b")
DATE_SLASH_YY_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2})\b")

RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
RU_MONTH_RE = re.compile(
    r"\b(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{2}|\d{4})\b",
    re.IGNORECASE,
)

BIRTH_HINTS = ("г.р", "г.р.", "год рождения", "дата рождения", "родил", "родилась", "birth")
HISTORY_HINTS = (
    "анамнез", "ранее", "предыду", "в прошлом", "прошл", "контроль", "повторить",
    "предыдущ", "сравнение", "динамик", "история", "наблюдение"
)
CONSULT_ANCHORS = (
    "дата первичного осмотра", "дата осмотра", "дата приема",
    "дата приёма", "дата визита", "осмотр", "прием", "приём", "консультац",
)
ULTRASOUND_ANCHORS = (
    "узи", "ультразвук", "ультразвуков", "исследовани", "протокол", "заключение",
)

CONSULT_PRIORITY_PATTERNS = [
    ("primary_exam_date", re.compile(
        r"(дата\s*(первичного\s*)?осмотра[^0-9]{0,80})"
        r"(\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4}))", re.IGNORECASE), 3),
    ("visit_date", re.compile(
        r"(дата\s*(приема|приёма|визита)[^0-9]{0,80})"
        r"(\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4}))", re.IGNORECASE), 3),
    ("exam_from", re.compile(
        r"(осмотр[^0-9]{0,80}от[^0-9]{0,20})"
        r"(\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4}))", re.IGNORECASE), 2),
    ("priem_from", re.compile(
        r"((прием|приём)[^0-9]{0,120}от[^0-9]{0,20})"
        r"(\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4}))", re.IGNORECASE), 3),
]

ULTRASOUND_PRIORITY_PATTERNS = [
    ("uzi_from", re.compile(
        r"(узи[^0-9]{0,160}от[^0-9]{0,25})"
        r"(\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4}))", re.IGNORECASE), 2),
    ("uzi_protocol_from", re.compile(
        r"((протокол[^0-9]{0,60})?(узи|ультразвук|ультразвуков)[^0-9]{0,200}от[^0-9]{0,25})"
        r"(\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4}))", re.IGNORECASE), 4),
    ("study_date", re.compile(
        r"(дата\s*(проведения|выполнения)?\s*(исследовани|узи|ультразвуков)[^0-9]{0,120})"
        r"(\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4}))", re.IGNORECASE), 4),
    ("uzi_date_generic", re.compile(
        r"(узи[^0-9]{0,160})(дата[^0-9]{0,40})"
        r"(\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4}))", re.IGNORECASE), 3),
]


def _convert_2digit_year(yy: int) -> int:
    return 1900 + yy if yy >= TWO_DIGIT_YEAR_CUTOFF else 2000 + yy


def safe_datetime(day: int, month: int, year: int) -> datetime | None:
    try:
        if year < MIN_YEAR or year > MAX_YEAR:
            return None
        return datetime(year, month, day)
    except Exception:
        return None


def parse_any_date_str(s: str) -> datetime | None:
    s = s.strip()
    m = DATE_DOT_YYYY_RE.search(s)
    if m:
        return safe_datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = DATE_SLASH_YYYY_RE.search(s)
    if m:
        return safe_datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = DATE_DOT_YY_RE.search(s)
    if m:
        return safe_datetime(int(m.group(1)), int(m.group(2)), _convert_2digit_year(int(m.group(3))))
    m = DATE_SLASH_YY_RE.search(s)
    if m:
        return safe_datetime(int(m.group(1)), int(m.group(2)), _convert_2digit_year(int(m.group(3))))
    return None


def docx_text(path: Path) -> str:
    doc = Document(str(path))
    parts: list[str] = []
    for p in doc.paragraphs:
        if p.text:
            parts.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                t = cell.text
                if t:
                    parts.append(t)
    return "\n".join(parts)


def has_any_hint_near(text_lower: str, pos: int, hints: tuple[str, ...], window: int) -> bool:
    start = max(0, pos - window)
    end = min(len(text_lower), pos + window)
    snippet = text_lower[start:end]
    return any(h in snippet for h in hints)


def collect_date_candidates(text: str) -> list[dict]:
    t = text.lower()
    out: list[dict] = []
    for regex, kind in [
        (DATE_DOT_YYYY_RE, "dot_yyyy"),
        (DATE_SLASH_YYYY_RE, "slash_yyyy"),
        (DATE_DOT_YY_RE, "dot_yy"),
        (DATE_SLASH_YY_RE, "slash_yy"),
    ]:
        for m in regex.finditer(t):
            day = int(m.group(1))
            month = int(m.group(2))
            year_raw = int(m.group(3))
            year = year_raw if len(m.group(3)) == 4 else _convert_2digit_year(year_raw)
            dt = safe_datetime(day, month, year)
            if dt is None:
                continue
            if has_any_hint_near(t, m.start(), BIRTH_HINTS, window=55):
                continue
            out.append({"pos": m.start(), "dt": dt, "raw_kind": kind})
    for m in RU_MONTH_RE.finditer(t):
        day = int(m.group(1))
        month_name = m.group(2).lower()
        yy = m.group(3)
        month = RU_MONTHS.get(month_name, 0)
        if month == 0:
            continue
        year = int(yy) if len(yy) == 4 else _convert_2digit_year(int(yy))
        dt = safe_datetime(day, month, year)
        if dt is None:
            continue
        if has_any_hint_near(t, m.start(), BIRTH_HINTS, window=65):
            continue
        out.append({"pos": m.start(), "dt": dt, "raw_kind": "ru_month"})
    out.sort(key=lambda x: x["pos"])
    return out


def score_candidate(text_lower: str, candidate_pos: int, doc_kind: str) -> int:
    score = 0
    if has_any_hint_near(text_lower, candidate_pos, HISTORY_HINTS, window=70):
        score -= 40
    if doc_kind == "consult":
        if has_any_hint_near(text_lower, candidate_pos, CONSULT_ANCHORS, window=90):
            score += 80
        if has_any_hint_near(text_lower, candidate_pos, ("дата первичного осмотра",), window=120):
            score += 60
        if has_any_hint_near(text_lower, candidate_pos, ("дата осмотра",), window=120):
            score += 40
        if has_any_hint_near(text_lower, candidate_pos, ("дата приема", "дата приёма", "дата визита"), window=120):
            score += 35
    else:
        if has_any_hint_near(text_lower, candidate_pos, ULTRASOUND_ANCHORS, window=120):
            score += 80
        if has_any_hint_near(text_lower, candidate_pos, ("узи",), window=140):
            score += 60
        if has_any_hint_near(text_lower, candidate_pos, ("дата исследования", "дата проведения", "дата выполнения"), window=160):
            score += 35
    if candidate_pos < 400:
        score += 10
    if candidate_pos < 200:
        score += 5
    return score


def doc_kind_from_visit_type(visit_type: str) -> str:
    vt = (visit_type or "unknown").strip().lower()
    if vt in {"ultrasound", "ultrasound_onco"}:
        return "ultrasound"
    return "consult"


def pick_from_priority_patterns(text: str, doc_kind: str) -> tuple[str | None, str]:
    t = text.lower()
    patterns = ULTRASOUND_PRIORITY_PATTERNS if doc_kind == "ultrasound" else CONSULT_PRIORITY_PATTERNS
    for rule, pattern, date_group in patterns:
        for m in pattern.finditer(t):
            date_str = m.group(date_group)
            dt = parse_any_date_str(date_str)
            if dt is None:
                continue
            if has_any_hint_near(t, m.start(date_group), BIRTH_HINTS, window=70):
                continue
            if has_any_hint_near(t, m.start(date_group), HISTORY_HINTS, window=80):
                continue
            return dt.date().isoformat(), rule
    return None, "none"


def choose_main_visit_date(text: str, visit_type: str) -> tuple[str | None, int, str, str]:
    doc_kind = doc_kind_from_visit_type(visit_type)
    exact, rule = pick_from_priority_patterns(text, doc_kind)
    if exact:
        candidates = collect_date_candidates(text)
        return exact, len(candidates), rule, "exact_anchor"
    candidates = collect_date_candidates(text)
    if not candidates:
        return None, 0, "none", "none"
    if len(candidates) == 1:
        return candidates[0]["dt"].date().isoformat(), 1, "fallback_single", "fallback_single"
    t = text.lower()
    best = None
    best_score = None
    for c in candidates:
        sc = score_candidate(t, c["pos"], doc_kind)
        if best_score is None or sc > best_score:
            best_score = sc
            best = c
        elif sc == best_score and best and c["pos"] < best["pos"]:
            best = c
    return best["dt"].date().isoformat(), len(candidates), "fallback_scored", "fallback_scored"


def infer_visit_type_for_unknown(original_vt: str, doc_kind: str, rule_used: str) -> str:
    vt = (original_vt or "unknown").strip().lower()
    if vt != "unknown":
        return vt
    if rule_used in {"primary_exam_date", "visit_date", "exam_from", "priem_from"}:
        return "consult"
    if rule_used in {"uzi_from", "uzi_protocol_from", "study_date", "uzi_date_generic"}:
        return "ultrasound"
    if rule_used in {"fallback_single", "fallback_scored"}:
        return "ultrasound" if doc_kind == "ultrasound" else "consult"
    return "unknown"


RU_MONTH_FOLDER = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
    "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12
}


def approx_from_month_year(row: dict) -> str | None:
    month_name = (row.get("month") or "").strip().lower().replace("ё", "е")
    year_str = (row.get("year") or "").strip()
    if not month_name or not year_str:
        return None
    m = RU_MONTH_FOLDER.get(month_name)
    if not m:
        return None
    try:
        y = int(year_str)
    except ValueError:
        return None
    dt = safe_datetime(1, m, y)
    return dt.date().isoformat() if dt else None


# ─────────────────────────────────────────────
# NEW: Clinical field extraction
# ─────────────────────────────────────────────

def _first_line_after(text: str, anchors: tuple[str, ...], max_chars: int = 300) -> str:
    """
    Find first anchor keyword in text, return the raw text that follows it
    (up to max_chars characters or the next newline-heavy section).
    Everything is returned as-is — dirty, unprocessed. That is intentional.
    """
    t_lower = text.lower()
    for anchor in anchors:
        pos = t_lower.find(anchor.lower())
        if pos == -1:
            continue
        # move past the anchor itself
        start = pos + len(anchor)
        # skip leading punctuation/spaces
        while start < len(text) and text[start] in " :\t-–—":
            start += 1
        chunk = text[start: start + max_chars]
        # cut at double newline (new section starts)
        chunk = re.split(r"\n{2,}", chunk)[0]
        return chunk.strip()
    return ""


def extract_clinical_fields(text: str) -> dict:
    """
    Extract raw clinical fields from document text.

    All values are returned as raw strings — messy, inconsistent, sometimes
    empty. This is intentional: the whole point is to give you real data
    cleaning work in pandas.

    Fields added to each row:
      birth_year            – year of birth (4 digits or '')
      menarche_age_raw      – e.g. '14', '13-14', 'не помнит'
      pregnancies_raw       – e.g. '3', '', '-'
      births_raw            – e.g. '1'
      abortions_raw         – e.g. '2', 'нет'
      miscarriages_raw      – e.g. '0', '-'
      breastfed_raw         – e.g. 'до года', '6 мес', 'нет', ''
      breastfed_complications_raw  – e.g. 'мастит', 'лактостаз правой мж', ''
      complaints_raw        – free text of complaints (первые 400 символов)
      diagnosis_raw         – free text of final diagnosis
      icd10_code            – e.g. 'N60.1', 'N63', '' — only first code found
      birads_raw            – e.g. 'BIRADS 1|2', 'BI-RADS 3', '2'
      nodular_formation_raw – e.g. 'не пальпируется', 'пальпируется узел 1 см'
      heredity_oncology_raw – raw heredity section text (oncology context)
      past_diabetes_raw     – text around diabetes mention
      past_thyroid_raw      – text around thyroid mention
      ca153_raw             – e.g. '12.5', '-', ''
      uzi_result_raw        – raw UZI conclusion text (первые 300 символов)
    """
    fields: dict = {}

    # ── birth_year ──────────────────────────────────────────────────────────
    # DOB is already extracted for HMAC. We re-extract it here to get birth_year.
    # We do NOT store full DOB — only the year, which is safe enough.
    m = DOB_RE.search(text)
    if not m:
        m = DOB_GR_RE.search(text)
    if m:
        dob_raw = m.group(1)
        iso = normalize_dob(dob_raw)
        if iso and len(iso) >= 4:
            try:
                y = int(iso[:4])
                fields["birth_year"] = str(y) if 1920 <= y <= 2010 else ""
            except ValueError:
                fields["birth_year"] = ""
        else:
            fields["birth_year"] = ""
    else:
        fields["birth_year"] = ""

    # ── menarche_age_raw ────────────────────────────────────────────────────
    # Looks for: "Менархе с 14 лет", "Менархе: 12", "Menarche 13"
    menarche_match = re.search(
        r"менарх[еэ]\s*[сc]?\s*[:\-]?\s*(\d{1,2}(?:[.\-]\d{1,2})?)",
        text, re.IGNORECASE
    )
    fields["menarche_age_raw"] = menarche_match.group(1).strip() if menarche_match else ""

    # ── reproductive counts ──────────────────────────────────────────────────
    # Pattern: "Беременности - 3 Родов- 1 абортов- 2 с/п выкидышей- 0"
    # All four often appear on the same line, so we search the whole text.

    preg_m = re.search(
        r"берем[её]нност[иь]\s*[-–—:]\s*(\d+|нет|-)",
        text, re.IGNORECASE
    )
    fields["pregnancies_raw"] = preg_m.group(1).strip() if preg_m else ""

    births_m = re.search(
        r"родов\s*[-–—:]\s*(\d+|нет|-)",
        text, re.IGNORECASE
    )
    fields["births_raw"] = births_m.group(1).strip() if births_m else ""

    abort_m = re.search(
        r"аборт[ао]в\s*[-–—:]\s*(\d+|нет|-)",
        text, re.IGNORECASE
    )
    fields["abortions_raw"] = abort_m.group(1).strip() if abort_m else ""

    misc_m = re.search(
        r"(?:с[/\\]п\s*)?выкидыш[еэей]{0,2}\s*[-–—:]\s*(\d+|нет|-)",
        text, re.IGNORECASE
    )
    fields["miscarriages_raw"] = misc_m.group(1).strip() if misc_m else ""

    # ── breastfed_raw ────────────────────────────────────────────────────────
    # "Кормила грудью: до года", "кормление грудью - 6 мес"
    bf_m = re.search(
        r"корм(?:ила|ление)[^:\n]{0,20}(?:грудью)?\s*[:\-–—]?\s*([^\n]{1,60})",
        text, re.IGNORECASE
    )
    fields["breastfed_raw"] = bf_m.group(1).strip() if bf_m else ""

    # ── breastfed_complications_raw ──────────────────────────────────────────
    compl_m = re.search(
        r"осложнени[яей][^:\n]{0,30}(?:кормлени[яей]|лактац)[^:\n]{0,20}[:\-–—]?\s*([^\n]{1,150})",
        text, re.IGNORECASE
    )
    if not compl_m:
        # fallback: line that mentions мастит or лактостаз
        compl_m = re.search(
            r"((?:мастит|лактостаз)[^\n]{0,120})",
            text, re.IGNORECASE
        )
    fields["breastfed_complications_raw"] = compl_m.group(1).strip() if compl_m else ""

    # ── complaints_raw ───────────────────────────────────────────────────────
    # "Жалобы на ..." — take up to 400 chars of free text
    complaints = _first_line_after(
        text,
        ("Жалобы на", "Жалобы:", "Жалобы", "Жалоб"),
        max_chars=400,
    )
    fields["complaints_raw"] = complaints[:400]

    # ── diagnosis_raw ────────────────────────────────────────────────────────
    # Look for the final diagnosis block; several header variants exist
    diagnosis = _first_line_after(
        text,
        (
            "Заключительный диагноз:",
            "Заключительный диагноз",
            "Основной диагноз:",
            "Основной диагноз",
            "Предварительный диагноз:",
            "диагноз:",
        ),
        max_chars=300,
    )
    fields["diagnosis_raw"] = diagnosis[:300]

    # ── icd10_code ───────────────────────────────────────────────────────────
    # ICD-10 codes look like N60.1, C50, D24 — letter + 2 digits + optional .digit
    icd_m = re.search(
        r"\b([A-Z]\d{2}(?:\.\d{1,2})?)\b",
        text
    )
    fields["icd10_code"] = icd_m.group(1).strip() if icd_m else ""

    # ── birads_raw ───────────────────────────────────────────────────────────
    # Very inconsistently written: "BIRADS 2", "BI-RADS 3", "Bi-Rads1|2", "бирадс 4"
    birads_m = re.search(
        r"(?:bi[-\s]?rads|бирадс|birads)\s*[:\-]?\s*([\d|/\\\s]{1,10})",
        text, re.IGNORECASE
    )
    fields["birads_raw"] = birads_m.group(1).strip() if birads_m else ""

    # ── nodular_formation_raw ────────────────────────────────────────────────
    nodular = _first_line_after(
        text,
        ("Узловые образования", "Объемные образования", "Узловое образование"),
        max_chars=200,
    )
    fields["nodular_formation_raw"] = nodular[:200]

    # ── heredity_oncology_raw ────────────────────────────────────────────────
    # Take the full heredity line — doctor writes free text like
    # "тетя рмж до 50 лет", "мать рак молочной железы", "не отягощен"
    heredity = _first_line_after(
        text,
        ("Наследственность", "Наследственный анамнез", "Heredity"),
        max_chars=300,
    )
    fields["heredity_oncology_raw"] = heredity[:300]

    # ── past_diabetes_raw ────────────────────────────────────────────────────
    # "сахарный диабет - отрицает", "сахарный диабет 2 типа"
    diab_m = re.search(
        r"сахарн[ыой]{1,2}\s+диабет[а-я]{0,4}[^\n]{0,80}",
        text, re.IGNORECASE
    )
    fields["past_diabetes_raw"] = diab_m.group(0).strip() if diab_m else ""

    # ── past_thyroid_raw ─────────────────────────────────────────────────────
    thyroid = _first_line_after(
        text,
        ("Заболевания щитовидной железы", "щитовидная железа", "щитовидной"),
        max_chars=150,
    )
    fields["past_thyroid_raw"] = thyroid[:150]

    # ── ca153_raw ────────────────────────────────────────────────────────────
    # "СА-15.3- 12.5 ед/мл", "CA 15-3: 18,3", "СА-15.3- - ед/мл" (empty = dash)
    ca_m = re.search(
        r"[сc][аa][-\s]?15[.\-]?3\s*[-–—:]\s*([\d.,\-–— ]{1,20})\s*(?:ед|u|ме)?",
        text, re.IGNORECASE
    )
    fields["ca153_raw"] = ca_m.group(1).strip() if ca_m else ""

    # ── uzi_result_raw ───────────────────────────────────────────────────────
    # Grab the УЗИ молочных желез result line(s) — raw, up to 300 chars
    uzi = _first_line_after(
        text,
        ("УЗИ молочных желез от", "УЗИ молочных желез", "Ультразвуковое исследование"),
        max_chars=300,
    )
    fields["uzi_result_raw"] = uzi[:300]

    return fields


# ─────────────────────────────────────────────
# Main (original logic + clinical fields added)
# ─────────────────────────────────────────────
def main() -> None:
    if not IN_CSV.exists():
        raise FileNotFoundError(f"Input CSV not found: {IN_CSV}")

    rows_out: list[dict] = []

    stats_source_before = Counter()
    stats_source_after = Counter()
    stats_quality = Counter()
    stats_rule = Counter()
    stats_errors = Counter()

    written = 0
    skipped_no_patient = 0
    skipped_bad_patient = 0

    processed = 0
    parsed_docx = 0
    found_exact_day = 0
    used_month_only = 0
    used_mtime = 0

    fio_source_stats = Counter()

    with IN_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no header")

        for i, row in enumerate(reader, 1):
            processed += 1
            if i % PROGRESS_EVERY == 0:
                print(
                    f"Processed {i} rows... docx:{parsed_docx} written:{written} "
                    f"skipped_no_patient:{skipped_no_patient}"
                )

            path = Path(row.get("path", ""))

            original_vt = (row.get("visit_type") or "unknown").strip().lower()
            before_source = (row.get("date_source") or "path").strip() or "path"
            stats_source_before[before_source] += 1

            if not path.exists():
                stats_errors["missing_file"] += 1
                skipped_no_patient += 1
                continue

            try:
                parsed_docx += 1
                text = docx_text(path)
            except Exception:
                stats_errors["docx_read_error"] += 1
                skipped_no_patient += 1
                continue

            # patient
            fio_raw, dob_raw, fio_source = extract_fio_and_dob(text, path)
            if not fio_raw or not dob_raw:
                skipped_no_patient += 1
                continue

            fio_source_stats[fio_source] += 1

            try:
                patient_id = make_patient_id(fio_raw, dob_raw)
                file_id = make_file_id(path)
            except Exception:
                skipped_bad_patient += 1
                continue

            if not patient_id:
                skipped_bad_patient += 1
                continue

            # dates
            visit_date = ""
            date_source = before_source
            date_rule_used = "none"
            date_quality = "none"
            candidates_count = 0

            try:
                best_date, cnt, rule_used, quality = choose_main_visit_date(text, original_vt)
                candidates_count = cnt
                date_rule_used = rule_used
                date_quality = quality

                if best_date:
                    visit_date = best_date
                    date_source = "docx"
                    found_exact_day += 1
                else:
                    approx = approx_from_month_year(row)
                    if approx:
                        visit_date = approx
                        date_source = before_source
                        date_quality = "month_only"
                        used_month_only += 1
                    else:
                        mtime = (row.get("mtime") or "").strip()
                        if mtime:
                            visit_date = mtime.split("T")[0]
                            date_source = "mtime"
                            date_quality = "mtime"
                            used_mtime += 1
                        else:
                            date_quality = "none"
            except Exception:
                stats_errors["date_extract_error"] += 1

            # infer unknown
            vt_inferred = original_vt
            vt_final = original_vt
            if original_vt == "unknown":
                vt_inferred = infer_visit_type_for_unknown(
                    original_vt, doc_kind_from_visit_type(original_vt), date_rule_used
                )
                vt_final = vt_inferred

            # NEW: clinical fields — wrapped in try/except so one bad file
            # never kills the whole run. On error: all fields become "".
            try:
                clinical = extract_clinical_fields(text)
            except Exception:
                stats_errors["clinical_extract_error"] += 1
                clinical = {
                    "birth_year": "", "menarche_age_raw": "",
                    "pregnancies_raw": "", "births_raw": "",
                    "abortions_raw": "", "miscarriages_raw": "",
                    "breastfed_raw": "", "breastfed_complications_raw": "",
                    "complaints_raw": "", "diagnosis_raw": "",
                    "icd10_code": "", "birads_raw": "",
                    "nodular_formation_raw": "", "heredity_oncology_raw": "",
                    "past_diabetes_raw": "", "past_thyroid_raw": "",
                    "ca153_raw": "", "uzi_result_raw": "",
                }

            # build SAFE output row (no path/filename)
            out_row = {}
            for k, v in row.items():
                if k.lower() in {"path", "filename"}:
                    continue
                out_row[k] = v

            out_row["file_id"] = file_id
            out_row["patient_id"] = patient_id
            out_row["fio_source"] = fio_source
            out_row["visit_date"] = visit_date
            out_row["date_source"] = date_source
            out_row["date_rule_used"] = date_rule_used
            out_row["date_quality"] = date_quality
            out_row["date_candidates_count"] = str(candidates_count)
            out_row["visit_type_inferred"] = vt_inferred
            out_row["visit_type_final"] = vt_final

            # append clinical fields at the end
            out_row.update(clinical)

            rows_out.append(out_row)
            written += 1

            stats_source_after[date_source] += 1
            stats_quality[date_quality] += 1
            stats_rule[date_rule_used] += 1

    if not rows_out:
        print("No rows written. Check PATIENT_ID_SECRET and patterns.")
        return

    fieldnames = list(rows_out[0].keys())
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    print("\nDone.")
    print("Processed rows:", processed)
    print("Docx parsed:", parsed_docx)
    print("Rows written:", written)
    print("Skipped (no FIO/DOB):", skipped_no_patient)
    print("Skipped (bad normalize/HMAC):", skipped_bad_patient)
    print("FIO source:", dict(fio_source_stats))
    print("Exact day from docx:", found_exact_day)
    print("Month-only approximations:", used_month_only)
    print("Used mtime fallback:", used_mtime)
    print("Saved:", OUT_CSV)

    print("\nDate source before:")
    for k, v in stats_source_before.most_common():
        print(f"  {k}: {v}")

    print("\nDate source after:")
    for k, v in stats_source_after.most_common():
        print(f"  {k}: {v}")

    print("\nDate quality:")
    for k, v in stats_quality.most_common():
        print(f"  {k}: {v}")

    print("\nRule used (overall):")
    for k, v in stats_rule.most_common():
        print(f"  {k}: {v}")

    if stats_errors:
        print("\nErrors (safe counts):")
        for k, v in stats_errors.most_common():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()