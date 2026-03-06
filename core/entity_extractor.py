"""
llm_clinical_notes — Medical Entity Extractor
===============================================
Rule-based + pattern-matching NER for clinical notes.
Extracts: diagnoses, medications, vitals, labs, procedures.
Applies NegEx algorithm for negation detection.

Author: swordenkisk | github.com/swordenkisk/llm_clinical_notes
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
from .code_mapper import CodeMapper, MedCode, AbbrevExpander


class EntityType(Enum):
    DIAGNOSIS  = "DIAGNOSIS"
    MEDICATION = "MEDICATION"
    VITAL      = "VITAL"
    LAB_RESULT = "LAB_RESULT"
    PROCEDURE  = "PROCEDURE"
    PATIENT    = "PATIENT"


@dataclass
class MedEntity:
    text        : str
    entity_type : EntityType
    value       : Optional[str]  = None   # numeric value if applicable
    unit        : Optional[str]  = None
    negated     : bool           = False
    code        : Optional[MedCode] = None
    raw_span    : str            = ""

    def __str__(self):
        neg  = " [NEGATED]" if self.negated else ""
        val  = f" = {self.value} {self.unit or ''}" if self.value else ""
        code = f" [{self.code.system}:{self.code.code}]" if self.code else ""
        return f"{self.entity_type.value}: {self.text}{val}{neg}{code}"


# ─── NegEx negation triggers ─────────────────────────────────────

NEGEX_PRE = [
    "no ", "not ", "denies ", "without ", "absent ", "negative for ",
    "ruled out ", "no evidence of ", "no sign of ", "free of ",
]
NEGEX_POST = [
    " not present", " absent", " negative", " unlikely", " ruled out",
]


def is_negated(sentence: str, entity: str) -> bool:
    s = sentence.lower()
    e = entity.lower()
    idx = s.find(e)
    if idx < 0:
        return False
    before = s[max(0, idx-40):idx]
    after  = s[idx+len(e):idx+len(e)+30]
    return any(before.endswith(n) or n in before[-20:] for n in NEGEX_PRE) or \
           any(after.startswith(n) or after[:20].find(n) >= 0 for n in NEGEX_POST)


# ─── Pattern Library ─────────────────────────────────────────────

VITAL_PATTERNS = [
    (r'bp\s*(\d{2,3})[/\\](\d{2,3})',          "blood pressure",    "{0}/{1}", "mmHg"),
    (r'hr\s*(\d{2,3})',                          "heart rate",        "{0}",     "bpm"),
    (r'rr\s*(\d{1,2})',                          "respiratory rate",  "{0}",     "/min"),
    (r'spo2\s*(\d{2,3})\s*%?',                  "oxygen saturation", "{0}",     "%"),
    (r'o2\s*sat\s*(\d{2,3})\s*%?',              "oxygen saturation", "{0}",     "%"),
    (r'(?:temp|t)\s*[\s:=]\s*(\d{2,3}(?:\.\d)?)',  "temperature",     "{0}",     "°C"),
]

LAB_PATTERNS = [
    (r'trop(?:onin)?\s*i?\s*(\d+\.?\d*)\s*(?:→|->|to|rising to)?\s*(\d+\.?\d*)?',
     "troponin i", None, "ng/mL"),
    (r'wbc\s*(\d+\.?\d*)',          "white blood cell count",  "{0}",  "×10⁹/L"),
    (r'hgb\s*(\d+\.?\d*)',          "hemoglobin",              "{0}",  "g/dL"),
    (r'cr(?:eat)?\s*(\d+\.?\d*)',   "creatinine",              "{0}",  "mg/dL"),
    (r'k\+?\s*(\d+\.?\d*)',         "potassium",               "{0}",  "mEq/L"),
    (r'na\+?\s*(\d+\.?\d*)',        "sodium",                  "{0}",  "mEq/L"),
    (r'bnp\s*(\d+\.?\d*)',          "b-type natriuretic peptide","{0}","pg/mL"),
    (r'a1c\s*(\d+\.?\d*)\s*%?',    "hemoglobin a1c",          "{0}",  "%"),
    (r'inr\s*(\d+\.?\d*)',          "international normalised ratio","{0}",""),
    (r'crp\s*(\d+\.?\d*)',          "c-reactive protein",      "{0}",  "mg/L"),
]

MED_PATTERNS = [
    (r'aspirin\s*(\d+\s*mg)?',          "aspirin"),
    (r'heparin\s*(?:iv\s*)?gtt',        "heparin"),
    (r'heparin\s*(?:\d+\s*units?)?',    "heparin"),
    (r'metformin\s*(\d+\s*mg)?',        "metformin"),
    (r'lisinopril\s*(\d+\s*mg)?',       "lisinopril"),
    (r'atorvastatin\s*(\d+\s*mg)?',     "atorvastatin"),
    (r'metoprolol\s*(\d+\s*mg)?',       "metoprolol"),
    (r'warfarin\s*(\d+\s*mg)?',         "warfarin"),
    (r'clopidogrel\s*(\d+\s*mg)?',      "clopidogrel"),
    (r'furosemide\s*(\d+\s*mg)?',       "furosemide"),
    (r'omeprazole\s*(\d+\s*mg)?',       "omeprazole"),
    (r'insulin\s*(?:\w+)?',             "insulin"),
    (r'salbutamol\s*(?:\d+\s*mcg)?',    "salbutamol"),
    (r'amlodipine\s*(\d+\s*mg)?',       "amlodipine"),
]

DIAGNOSIS_TERMS = [
    "hypertension", "htn", "diabetes", "dm2", "dm1",
    "coronary artery disease", "cad", "chest pain",
    "acute coronary syndrome", "acs",
    "myocardial infarction", "stemi", "nstemi",
    "atrial fibrillation", "afib",
    "heart failure", "chf",
    "pulmonary embolism",
    "deep vein thrombosis", "dvt",
    "stroke", "cva", "tia",
    "copd", "asthma",
    "urinary tract infection", "uti",
    "chronic kidney disease", "ckd",
    "tuberculosis", "tb",
    "st depression", "st elevation",
]

PROCEDURE_TERMS = [
    "ecg", "ekg", "echo", "echocardiogram", "electrocardiogram",
    "cxr", "chest x-ray", "chest xr",
    "ct scan", "mri", "ultrasound",
    "cardiac cath", "cath", "catheterisation",
    "pci", "cabg",
    "cardiology consult", "consult",
    "intubation",
]


# ─── Entity Extractor ─────────────────────────────────────────────

class EntityExtractor:
    """
    Rule-based medical NER with NegEx negation detection.
    Extracts all clinically relevant entities from a note.
    """

    def __init__(self):
        self.code_mapper = CodeMapper()
        self.expander    = AbbrevExpander()

    def extract(self, text: str) -> List[MedEntity]:
        text_lower = text.lower()
        entities   = []

        entities += self._extract_vitals(text_lower, text)
        entities += self._extract_labs(text_lower, text)
        entities += self._extract_medications(text_lower, text)
        entities += self._extract_diagnoses(text_lower, text)
        entities += self._extract_procedures(text_lower, text)
        entities += self._extract_patient_info(text)

        return entities

    def _extract_vitals(self, text_lower: str, original: str) -> List[MedEntity]:
        entities = []
        for pattern, name, fmt, unit in VITAL_PATTERNS:
            for m in re.finditer(pattern, text_lower):
                groups = m.groups()
                value  = fmt.format(*[g for g in groups if g]) if groups else None
                e = MedEntity(
                    text        = name,
                    entity_type = EntityType.VITAL,
                    value       = value,
                    unit        = unit,
                    negated     = False,
                    code        = self.code_mapper.lookup(name),
                    raw_span    = m.group(),
                )
                entities.append(e)
        return entities

    def _extract_labs(self, text_lower: str, original: str) -> List[MedEntity]:
        entities = []
        for pattern, name, fmt, unit in LAB_PATTERNS:
            for m in re.finditer(pattern, text_lower):
                groups = [g for g in m.groups() if g]
                if fmt and groups:
                    value = fmt.format(*groups)
                elif groups:
                    # Troponin with trend
                    value = " → ".join(groups)
                else:
                    value = None
                e = MedEntity(
                    text        = name,
                    entity_type = EntityType.LAB_RESULT,
                    value       = value,
                    unit        = unit,
                    negated     = is_negated(text_lower, name),
                    code        = self.code_mapper.lookup(name),
                    raw_span    = m.group(),
                )
                entities.append(e)
        return entities

    def _extract_medications(self, text_lower: str, original: str) -> List[MedEntity]:
        entities = []
        for pattern, name in MED_PATTERNS:
            for m in re.finditer(pattern, text_lower):
                dose = m.group(1) if m.lastindex and m.lastindex >= 1 else None
                e = MedEntity(
                    text        = name,
                    entity_type = EntityType.MEDICATION,
                    value       = dose,
                    unit        = None,
                    negated     = is_negated(text_lower, name),
                    code        = self.code_mapper.lookup(name),
                    raw_span    = m.group(),
                )
                entities.append(e)
        return entities

    def _extract_diagnoses(self, text_lower: str, original: str) -> List[MedEntity]:
        entities = []
        seen = set()
        for term in DIAGNOSIS_TERMS:
            if term in text_lower and term not in seen:
                seen.add(term)
                # Expand abbreviation to full name for code lookup
                full = self.expander.get_expansion(term) or term
                e = MedEntity(
                    text        = full,
                    entity_type = EntityType.DIAGNOSIS,
                    negated     = is_negated(text_lower, term),
                    code        = self.code_mapper.lookup(full) or self.code_mapper.lookup(term),
                    raw_span    = term,
                )
                entities.append(e)
        return entities

    def _extract_procedures(self, text_lower: str, original: str) -> List[MedEntity]:
        entities = []
        seen = set()
        for term in PROCEDURE_TERMS:
            if term in text_lower and term not in seen:
                seen.add(term)
                full = self.expander.get_expansion(term) or term
                e = MedEntity(
                    text        = full,
                    entity_type = EntityType.PROCEDURE,
                    negated     = is_negated(text_lower, term),
                    code        = self.code_mapper.lookup(full),
                    raw_span    = term,
                )
                entities.append(e)
        return entities

    def _extract_patient_info(self, text: str) -> List[MedEntity]:
        entities = []
        # Age + sex pattern: "67yo M", "45 year old female", "Pt 52F"
        m = re.search(r'(?:pt\.?\s*)?(\d{1,3})\s*(?:yo|y\.?o\.?|year[s]?\s+old)\s*([MmFf])', text, re.I)
        if m:
            entities.append(MedEntity(
                text        = f"{m.group(1)}-year-old {('male' if m.group(2).upper()=='M' else 'female')}",
                entity_type = EntityType.PATIENT,
                raw_span    = m.group(),
            ))
        return entities

    def summary(self, entities: List[MedEntity]) -> str:
        from collections import Counter
        counts = Counter(e.entity_type.value for e in entities)
        coded  = sum(1 for e in entities if e.code)
        neg    = sum(1 for e in entities if e.negated)
        return (
            f"Entities extracted: {len(entities)} total\n"
            + "\n".join(f"  {k:15s}: {v}" for k, v in counts.items())
            + f"\n  Coded           : {coded}/{len(entities)}"
            + f"\n  Negated         : {neg}"
        )
