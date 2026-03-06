"""
llm_clinical_notes — FHIR R4 Builder
======================================
Converts extracted medical entities into valid FHIR R4 resources.

FHIR R4 resources generated:
  Patient              — demographics
  Condition            — diagnoses
  MedicationRequest    — prescriptions
  Observation          — vitals + lab results
  Procedure            — clinical procedures
  Bundle               — wraps all resources

Reference: https://hl7.org/fhir/R4/

Author: swordenkisk | github.com/swordenkisk/llm_clinical_notes
"""

import json
import hashlib
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from llm_clinical_notes.core.entity_extractor import MedEntity, EntityType


def _uuid(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:8] + "-" + \
           hashlib.sha256((seed+"x").encode()).hexdigest()[:4] + "-4" + \
           hashlib.sha256((seed+"y").encode()).hexdigest()[:3] + "-a" + \
           hashlib.sha256((seed+"z").encode()).hexdigest()[:3] + "-" + \
           hashlib.sha256((seed+"w").encode()).hexdigest()[:12]


class FHIRBuilder:
    """Builds FHIR R4 resources from extracted medical entities."""

    BASE = "https://swordenkisk.github.io/llm_clinical_notes/fhir"

    def __init__(self, patient_id: str = "patient-001"):
        self.patient_id  = patient_id
        self.date        = "2026-03-06"
        self.resources   : List[Dict] = []

    def build_bundle(self, entities: List[MedEntity], note_text: str = "") -> Dict:
        """Build a complete FHIR R4 Bundle from all entities."""
        self.resources = []

        # Patient resource
        patient = self._build_patient(entities)
        self.resources.append(patient)

        for e in entities:
            if e.negated:
                continue  # Don't record negated findings
            if e.entity_type == EntityType.DIAGNOSIS:
                self.resources.append(self._build_condition(e))
            elif e.entity_type == EntityType.MEDICATION:
                self.resources.append(self._build_medication_request(e))
            elif e.entity_type in (EntityType.VITAL, EntityType.LAB_RESULT):
                self.resources.append(self._build_observation(e))
            elif e.entity_type == EntityType.PROCEDURE:
                self.resources.append(self._build_procedure(e))

        bundle = {
            "resourceType" : "Bundle",
            "id"           : _uuid("bundle-" + self.date),
            "type"         : "collection",
            "timestamp"    : self.date + "T00:00:00Z",
            "meta"         : {
                "profile": [f"{self.BASE}/StructureDefinition/clinical-notes-bundle"]
            },
            "entry"        : [
                {"resource": r, "fullUrl": f"{self.BASE}/{r['resourceType']}/{r['id']}"}
                for r in self.resources
            ],
        }
        return bundle

    # ── Individual Resource Builders ─────────────────────────────

    def _build_patient(self, entities: List[MedEntity]) -> Dict:
        pat = next((e for e in entities if e.entity_type == EntityType.PATIENT), None)
        age, gender = "unknown", "unknown"
        if pat:
            import re
            m = re.search(r'(\d+)-year-old\s+(male|female)', pat.text)
            if m:
                age, gender = m.group(1), m.group(2)

        return {
            "resourceType" : "Patient",
            "id"           : self.patient_id,
            "meta"         : {"profile": ["http://hl7.org/fhir/StructureDefinition/Patient"]},
            "identifier"   : [{"system": f"{self.BASE}/patient", "value": self.patient_id}],
            "gender"       : gender,
            "extension"    : [{"url": "http://hl7.org/fhir/StructureDefinition/patient-age",
                               "valueString": age}],
        }

    def _build_condition(self, entity: MedEntity) -> Dict:
        coding = [entity.code.to_fhir_coding()] if entity.code else []
        return {
            "resourceType"  : "Condition",
            "id"            : _uuid("cond-" + entity.text),
            "clinicalStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": "active", "display": "Active"}]
            },
            "verificationStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                            "code": "confirmed"}]
            },
            "code"    : {"coding": coding, "text": entity.text},
            "subject" : {"reference": f"Patient/{self.patient_id}"},
            "recordedDate": self.date,
        }

    def _build_medication_request(self, entity: MedEntity) -> Dict:
        coding = [entity.code.to_fhir_coding()] if entity.code else []
        return {
            "resourceType"  : "MedicationRequest",
            "id"            : _uuid("medrx-" + entity.text),
            "status"        : "active",
            "intent"        : "order",
            "medicationCodeableConcept": {"coding": coding, "text": entity.text},
            "subject"       : {"reference": f"Patient/{self.patient_id}"},
            "authoredOn"    : self.date,
            "dosageInstruction": [{"text": entity.value or "as prescribed"}],
        }

    def _build_observation(self, entity: MedEntity) -> Dict:
        coding = [entity.code.to_fhir_coding()] if entity.code else []
        obs = {
            "resourceType"  : "Observation",
            "id"            : _uuid("obs-" + entity.text),
            "status"        : "final",
            "category"      : [{
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs" if entity.entity_type == EntityType.VITAL else "laboratory",
                            "display": "Vital Signs" if entity.entity_type == EntityType.VITAL else "Laboratory"}]
            }],
            "code"          : {"coding": coding, "text": entity.text},
            "subject"       : {"reference": f"Patient/{self.patient_id}"},
            "effectiveDateTime": self.date,
        }
        if entity.value:
            # Try to parse numeric value
            import re
            nums = re.findall(r'\d+\.?\d*', entity.value)
            if nums:
                obs["valueQuantity"] = {
                    "value" : float(nums[0]),
                    "unit"  : entity.unit or "",
                    "system": "http://unitsofmeasure.org",
                }
                if "/" in (entity.value or "") and len(nums) >= 2:
                    obs["component"] = [
                        {"code": {"text": "systolic"},
                         "valueQuantity": {"value": float(nums[0]), "unit": "mmHg"}},
                        {"code": {"text": "diastolic"},
                         "valueQuantity": {"value": float(nums[1]), "unit": "mmHg"}},
                    ]
        return obs

    def _build_procedure(self, entity: MedEntity) -> Dict:
        coding = [entity.code.to_fhir_coding()] if entity.code else []
        return {
            "resourceType"  : "Procedure",
            "id"            : _uuid("proc-" + entity.text),
            "status"        : "completed",
            "code"          : {"coding": coding, "text": entity.text},
            "subject"       : {"reference": f"Patient/{self.patient_id}"},
            "performedDateTime": self.date,
        }


class FHIRValidator:
    """Validates FHIR R4 bundle structure."""

    REQUIRED_FIELDS = {
        "Bundle"             : ["resourceType", "type", "entry"],
        "Patient"            : ["resourceType", "id"],
        "Condition"          : ["resourceType", "id", "clinicalStatus", "code", "subject"],
        "MedicationRequest"  : ["resourceType", "id", "status", "intent",
                                "medicationCodeableConcept", "subject"],
        "Observation"        : ["resourceType", "id", "status", "code", "subject"],
        "Procedure"          : ["resourceType", "id", "status", "code", "subject"],
    }

    def validate(self, bundle: Dict) -> "ValidationResult":
        errors, warnings = [], []

        if bundle.get("resourceType") != "Bundle":
            errors.append("Root must be resourceType=Bundle")
            return ValidationResult(False, errors, warnings)

        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            rtype    = resource.get("resourceType", "Unknown")
            required = self.REQUIRED_FIELDS.get(rtype, [])
            for f in required:
                if f not in resource:
                    errors.append(f"{rtype}/{resource.get('id','?')}: missing '{f}'")

        valid = len(errors) == 0
        if valid:
            n = len(bundle.get("entry", []))
            warnings.append(f"Bundle contains {n} resources — all fields present")
        return ValidationResult(valid, errors, warnings)


@dataclass
class ValidationResult:
    valid    : bool
    errors   : List[str]
    warnings : List[str]

    def __str__(self):
        s = "✅ VALID" if self.valid else "❌ INVALID"
        if self.errors:
            s += "\n  Errors: " + "; ".join(self.errors)
        if self.warnings:
            s += "\n  Info: " + "; ".join(self.warnings)
        return s
