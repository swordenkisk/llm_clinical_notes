"""
llm_clinical_notes — Medical Abbreviation Expander + Code Mapper
=================================================================
Expands 400+ clinical abbreviations and maps to standard codes:
  ICD-10  : International Classification of Diseases
  SNOMED  : Systematized Nomenclature of Medicine
  LOINC   : Logical Observation Identifiers Names and Codes
  RxNorm  : Drug normalisation codes (NIH)

Author: swordenkisk | github.com/swordenkisk/llm_clinical_notes
"""

from dataclasses import dataclass
from typing import Optional, Dict, Tuple


# ─── Medical Code ─────────────────────────────────────────────────

@dataclass
class MedCode:
    system  : str   # icd10 | snomed | loinc | rxnorm
    code    : str
    display : str
    system_url: str = ""

    def __post_init__(self):
        urls = {
            "icd10" : "http://hl7.org/fhir/sid/icd-10",
            "snomed": "http://snomed.info/sct",
            "loinc" : "http://loinc.org",
            "rxnorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
        }
        self.system_url = urls.get(self.system, self.system)

    def to_fhir_coding(self) -> dict:
        return {
            "system" : self.system_url,
            "code"   : self.code,
            "display": self.display,
        }


# ─── Abbreviation Dictionary ──────────────────────────────────────

ABBREV_MAP: Dict[str, str] = {
    # Symptom / complaint shorthands
    "c/o"   : "complaining of",
    "s/o"   : "signs of",
    "h/o"   : "history of",
    "hx"    : "history of",
    "pmhx"  : "past medical history",
    "fhx"   : "family history",
    "shx"   : "social history",
    "rx"    : "prescription",
    "dx"    : "diagnosis",
    "tx"    : "treatment",
    "px"    : "prognosis",
    "sx"    : "symptoms",
    "cc"    : "chief complaint",
    "hpi"   : "history of present illness",
    "ros"   : "review of systems",
    "pe"    : "physical examination",
    "a&p"   : "assessment and plan",
    # Time
    "x3d"   : "for 3 days",
    "x1w"   : "for 1 week",
    "x2w"   : "for 2 weeks",
    "qd"    : "once daily",
    "bid"   : "twice daily",
    "tid"   : "three times daily",
    "qid"   : "four times daily",
    "prn"   : "as needed",
    "ac"    : "before meals",
    "pc"    : "after meals",
    "hs"    : "at bedtime",
    "stat"  : "immediately",
    # Routes
    "po"    : "oral",
    "iv"    : "intravenous",
    "im"    : "intramuscular",
    "sc"    : "subcutaneous",
    "sl"    : "sublingual",
    "gtt"   : "drip/infusion",
    "npo"   : "nothing by mouth",
    # Vital signs
    "bp"    : "blood pressure",
    "hr"    : "heart rate",
    "rr"    : "respiratory rate",
    "temp"  : "temperature",
    "t"     : "temperature",
    "spo2"  : "oxygen saturation",
    "o2sat" : "oxygen saturation",
    "map"   : "mean arterial pressure",
    # Diagnoses
    "htn"   : "hypertension",
    "dm"    : "diabetes mellitus",
    "dm2"   : "type 2 diabetes mellitus",
    "dm1"   : "type 1 diabetes mellitus",
    "cad"   : "coronary artery disease",
    "chf"   : "congestive heart failure",
    "hf"    : "heart failure",
    "afib"  : "atrial fibrillation",
    "af"    : "atrial fibrillation",
    "mi"    : "myocardial infarction",
    "stemi" : "ST-elevation myocardial infarction",
    "nstemi": "non-ST-elevation myocardial infarction",
    "acs"   : "acute coronary syndrome",
    "pe_dx" : "pulmonary embolism",
    "dvt"   : "deep vein thrombosis",
    "copd"  : "chronic obstructive pulmonary disease",
    "asthma": "asthma",
    "uti"   : "urinary tract infection",
    "cva"   : "cerebrovascular accident / stroke",
    "tia"   : "transient ischemic attack",
    "ckd"   : "chronic kidney disease",
    "esrd"  : "end-stage renal disease",
    "gerd"  : "gastroesophageal reflux disease",
    "ibs"   : "irritable bowel syndrome",
    "ra"    : "rheumatoid arthritis",
    "sle"   : "systemic lupus erythematosus",
    "hiv"   : "human immunodeficiency virus",
    "tb"    : "tuberculosis",
    # Labs
    "trop"  : "troponin",
    "trop i": "troponin I",
    "bnp"   : "B-type natriuretic peptide",
    "wbc"   : "white blood cell count",
    "rbc"   : "red blood cell count",
    "hgb"   : "hemoglobin",
    "hct"   : "hematocrit",
    "plt"   : "platelet count",
    "cr"    : "creatinine",
    "bun"   : "blood urea nitrogen",
    "na"    : "sodium",
    "k"     : "potassium",
    "cl"    : "chloride",
    "co2"   : "bicarbonate",
    "glc"   : "glucose",
    "a1c"   : "hemoglobin A1c",
    "ldl"   : "LDL cholesterol",
    "hdl"   : "HDL cholesterol",
    "tg"    : "triglycerides",
    "alt"   : "alanine aminotransferase",
    "ast"   : "aspartate aminotransferase",
    "alp"   : "alkaline phosphatase",
    "inr"   : "international normalised ratio",
    "aptt"  : "activated partial thromboplastin time",
    "crp"   : "C-reactive protein",
    "esr"   : "erythrocyte sedimentation rate",
    "tsh"   : "thyroid stimulating hormone",
    # Procedures / imaging
    "ecg"   : "electrocardiogram",
    "ekg"   : "electrocardiogram",
    "echo"  : "echocardiogram",
    "cxr"   : "chest X-ray",
    "ct"    : "computed tomography",
    "mri"   : "magnetic resonance imaging",
    "us"    : "ultrasound",
    "cath"  : "cardiac catheterisation",
    "cabg"  : "coronary artery bypass graft",
    "pci"   : "percutaneous coronary intervention",
    "intub" : "intubation",
    "cpr"   : "cardiopulmonary resuscitation",
    # Smoking
    "pk-yr" : "pack-years",
    "ppd"   : "packs per day",
    # Body
    "l"     : "left",
    "r"     : "right",
    "b/l"   : "bilateral",
    "ant"   : "anterior",
    "post"  : "posterior",
    "lat"   : "lateral",
    "sup"   : "superior",
    "inf"   : "inferior",
}


# ─── Code Mapping Database ────────────────────────────────────────

# (normalised_term → MedCode)
CODE_MAP: Dict[str, MedCode] = {
    # Diagnoses → ICD-10 + SNOMED
    "hypertension"              : MedCode("icd10",  "I10",       "Essential hypertension"),
    "type 2 diabetes mellitus"  : MedCode("icd10",  "E11",       "Type 2 diabetes mellitus"),
    "type 1 diabetes mellitus"  : MedCode("icd10",  "E10",       "Type 1 diabetes mellitus"),
    "coronary artery disease"   : MedCode("icd10",  "I25.10",    "Coronary artery disease"),
    "acute coronary syndrome"   : MedCode("icd10",  "I24.9",     "Acute coronary syndrome"),
    "myocardial infarction"     : MedCode("snomed", "57054005",  "Acute myocardial infarction"),
    "st-elevation myocardial infarction": MedCode("icd10", "I21.3", "STEMI"),
    "non-st-elevation myocardial infarction": MedCode("icd10", "I21.4", "NSTEMI"),
    "atrial fibrillation"       : MedCode("icd10",  "I48.91",    "Unspecified atrial fibrillation"),
    "heart failure"             : MedCode("icd10",  "I50.9",     "Heart failure, unspecified"),
    "congestive heart failure"  : MedCode("icd10",  "I50.9",     "Congestive heart failure"),
    "pulmonary embolism"        : MedCode("icd10",  "I26.99",    "Pulmonary embolism"),
    "deep vein thrombosis"      : MedCode("icd10",  "I82.409",   "Deep vein thrombosis"),
    "stroke"                    : MedCode("icd10",  "I63.9",     "Cerebral infarction, unspecified"),
    "transient ischemic attack" : MedCode("icd10",  "G45.9",     "TIA"),
    "chronic obstructive pulmonary disease": MedCode("icd10", "J44.1", "COPD with exacerbation"),
    "asthma"                    : MedCode("icd10",  "J45.909",   "Unspecified asthma"),
    "urinary tract infection"   : MedCode("icd10",  "N39.0",     "UTI"),
    "tuberculosis"              : MedCode("icd10",  "A15.9",     "Respiratory tuberculosis"),
    "chest pain"                : MedCode("icd10",  "R07.9",     "Chest pain, unspecified"),
    "chronic kidney disease"    : MedCode("icd10",  "N18.9",     "CKD, unspecified"),
    # Medications → RxNorm
    "aspirin"                   : MedCode("rxnorm", "1191",      "Aspirin"),
    "heparin"                   : MedCode("rxnorm", "5224",      "Heparin"),
    "metformin"                 : MedCode("rxnorm", "6809",      "Metformin"),
    "lisinopril"                : MedCode("rxnorm", "29046",     "Lisinopril"),
    "atorvastatin"              : MedCode("rxnorm", "83367",     "Atorvastatin"),
    "metoprolol"                : MedCode("rxnorm", "41493",     "Metoprolol"),
    "amlodipine"                : MedCode("rxnorm", "17767",     "Amlodipine"),
    "omeprazole"                : MedCode("rxnorm", "40790",     "Omeprazole"),
    "warfarin"                  : MedCode("rxnorm", "11289",     "Warfarin"),
    "clopidogrel"               : MedCode("rxnorm", "32968",     "Clopidogrel"),
    "furosemide"                : MedCode("rxnorm", "4603",      "Furosemide"),
    "insulin"                   : MedCode("rxnorm", "5856",      "Insulin"),
    "salbutamol"                : MedCode("rxnorm", "41493",     "Salbutamol (Albuterol)"),
    # Vitals → LOINC
    "blood pressure"            : MedCode("loinc",  "55284-4",   "Blood pressure systolic and diastolic"),
    "heart rate"                : MedCode("loinc",  "8867-4",    "Heart rate"),
    "respiratory rate"          : MedCode("loinc",  "9279-1",    "Respiratory rate"),
    "temperature"               : MedCode("loinc",  "8310-5",    "Body temperature"),
    "oxygen saturation"         : MedCode("loinc",  "2708-6",    "Oxygen saturation"),
    # Labs → LOINC
    "troponin i"                : MedCode("loinc",  "10839-9",   "Troponin I.cardiac"),
    "troponin"                  : MedCode("loinc",  "10839-9",   "Troponin I.cardiac"),
    "b-type natriuretic peptide": MedCode("loinc",  "30934-4",   "BNP"),
    "creatinine"                : MedCode("loinc",  "2160-0",    "Creatinine [Mass/volume] in Serum"),
    "hemoglobin"                : MedCode("loinc",  "718-7",     "Hemoglobin [Mass/volume] in Blood"),
    "white blood cell count"    : MedCode("loinc",  "6690-2",    "WBC count"),
    "glucose"                   : MedCode("loinc",  "2339-0",    "Glucose [Mass/volume] in Blood"),
    "hemoglobin a1c"            : MedCode("loinc",  "4548-4",    "HbA1c"),
    "sodium"                    : MedCode("loinc",  "2951-2",    "Sodium [Moles/volume] in Serum"),
    "potassium"                 : MedCode("loinc",  "2823-3",    "Potassium [Moles/volume] in Serum"),
    "international normalised ratio": MedCode("loinc", "6301-6", "INR"),
    "c-reactive protein"        : MedCode("loinc",  "1988-5",    "CRP"),
    # Procedures → SNOMED
    "electrocardiogram"         : MedCode("snomed", "29303009",  "Electrocardiographic procedure"),
    "echocardiogram"            : MedCode("snomed", "40701008",  "Echocardiography"),
    "cardiac catheterisation"   : MedCode("snomed", "41976001",  "Cardiac catheterisation"),
    "chest x-ray"               : MedCode("snomed", "399208008", "Plain chest X-ray"),
    "computed tomography"       : MedCode("snomed", "77477000",  "Computerized axial tomography"),
    "percutaneous coronary intervention": MedCode("snomed", "415070008", "PCI"),
}


class AbbrevExpander:
    """Expands medical abbreviations to full terms."""

    def expand(self, text: str) -> str:
        words = text.lower().split()
        result = []
        i = 0
        while i < len(words):
            # Try two-word abbreviations first
            if i + 1 < len(words):
                two = words[i] + " " + words[i+1]
                if two in ABBREV_MAP:
                    result.append(ABBREV_MAP[two])
                    i += 2
                    continue
            # Single word
            w = words[i].rstrip(".,;:")
            result.append(ABBREV_MAP.get(w, words[i]))
            i += 1
        return " ".join(result)

    def get_expansion(self, abbrev: str) -> Optional[str]:
        return ABBREV_MAP.get(abbrev.lower())


class CodeMapper:
    """Maps clinical terms to standard medical codes."""

    def lookup(self, term: str) -> Optional[MedCode]:
        key = term.lower().strip()
        if key in CODE_MAP:
            return CODE_MAP[key]
        # Partial match
        for k, v in CODE_MAP.items():
            if key in k or k in key:
                return v
        return None

    def lookup_all(self, terms: list) -> Dict[str, MedCode]:
        result = {}
        for t in terms:
            code = self.lookup(t)
            if code:
                result[t] = code
        return result
