import unicodedata
import re
from rapidfuzz import fuzz

from .utils import get_exclusion_terms


# Dictionary of diagnostic abbreviations and their expanded forms
EXTENDED_DIAGNOSTICS: dict[str, str] = {
    "LES": "Lupus eritematoso sistémico",
    "PMR": "Polimialgia reumática",
    "AIJ": "Artritis idiopática juvenil",
    "ACG": "Arteritis de células gigantes",
    "SAF": "Síndrome antifosfolípido",
    "EMTC": "Enfermedad mixta del tejido conectivo",
    "EPID": "Enfermedad pulmonar intersticial difusa",
    "EII": "Enfermedad inflamatoria intestinal",
    "Lumbalgia": "Dolor en la parte inferior de la espalda",
    "Osteoartritis": "Artrosis",
    "Artralgias": "Dolor articular",
    "Gonalgia": "Dolor en la rodilla",
    "Trocanteritis": "Bursitis del trocánter mayor",
    "Dorsalgia": "Dolor en la parte superior de la espalda",
    "Mialgias": "Dolor muscular",
    "Cervicobraquialgia": "Síndrome cervicobraquial",
    "Dedo en resorte": "Tenosinovitis estenosante",
    "Enfermedad de Paget ósea": "Osteítis deformante",
    "Discopatía": "Trastorno degenerativo del disco intervertebral",
    "Artralgias mecánicas": "Dolor articular",
    "Coxalgia": "Dolor en la cadera",
    "Esclerodermia": "Esclerosis sistémica",
    "Omalgia": "Dolor en el hombro",
    "Quiste poplíteo": "Quiste de Baker",
    "Mal apoyo plantar": "Trastorno del pie",
    "Lumbartrosis": "Artrosis de la región lumbar",
    "Fibrodisplasia osificante progresiva": "Fibrodisplasia osificante progresiva",
    "Coxopatía": "Trastorno de la cadera",
    "Enfermedad de Dupuytren": "Contractura de Dupuytren",
    "Enfermedad autoinflamatoria": "Trastorno autoinflamatorio",
}

# Threshold for similarity scores to consider diagnoses as matching
SIMILARITY_THRESHOLD: float = 70.0


class Validator:
    def __init__(self):
        pass

    def _normalize_name(self, diagnostic: str) -> str:
        expanded_name = EXTENDED_DIAGNOSTICS.get(diagnostic, diagnostic)

        # Normalize: remove accents, convert to lowercase
        normalized = "".join(
            c
            for c in unicodedata.normalize("NFKD", expanded_name)
            if not unicodedata.combining(c)
        ).lower()

        # Remove punctuation and special characters
        normalized = re.sub(r"[^\w\s]", " ", normalized)

        # Remove multiple spaces and spaces at beginning/end
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def _tokenize_diagnosis(self, diagnosis: str) -> list[str]:
        tokens = diagnosis.split()

        # Remove exclusion terms
        return [token for token in tokens if token not in get_exclusion_terms()]

    def _calculate_similarity_scores(
        self, generated_diagnostic: str, correct_diagnostic: str
    ) -> tuple[float, float, float]:
        ratio = fuzz.ratio(generated_diagnostic, correct_diagnostic)
        partial_ratio = fuzz.partial_ratio(
            generated_diagnostic, correct_diagnostic)
        token_sort_ratio = fuzz.token_sort_ratio(
            generated_diagnostic, correct_diagnostic
        )

        return (ratio, partial_ratio, token_sort_ratio)

    def _is_invalid(self, diag):
        return diag is None or (isinstance(diag, str) and diag.strip() == "")

    def _validation_sequence(self, generated_diagnostic: str, correct_diagnostic: str) -> bool:
        # 1. Direct match after normalization
        if generated_diagnostic == correct_diagnostic:
            return True

        # 2. Check if all key terms in correct diagnosis are in processed diagnosis
        generated_terms = set(self._tokenize_diagnosis(generated_diagnostic))
        correct_terms = set(self._tokenize_diagnosis(correct_diagnostic))
        if len(correct_terms) > 0 and correct_terms.issubset(generated_terms):
            return True

        # 3. Using fuzzy string matching with various similarity metrics
        ratio, partial_ratio, token_sort_ratio = self._calculate_similarity_scores(
            generated_diagnostic, correct_diagnostic
        )
        if max(ratio, token_sort_ratio) >= SIMILARITY_THRESHOLD:
            return True
        if len(correct_diagnostic) < 15 and partial_ratio >= 90:
            return True

        # 4. Special case for substring relationships
        if len(correct_diagnostic) > 10 and len(generated_diagnostic) > 10:
            if (correct_diagnostic in generated_diagnostic) or (
                generated_diagnostic in correct_diagnostic
            ):
                return True
        return False

    def validate(self, generated_diagnostic: str, correct_diagnostic: str) -> bool:
        # Handle invalid cases
        if self._is_invalid(generated_diagnostic):
            return False
        if self._is_invalid(correct_diagnostic):
            return False

        # Normalize both diagnoses
        normalized_generated_diag = self._normalize_name(generated_diagnostic)
        normalized_correct_diag = self._normalize_name(correct_diagnostic)

        return self._validation_sequence(normalized_generated_diag, normalized_correct_diag)
