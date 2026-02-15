import re

import pandas as pd
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import BaseOutputParser, StrOutputParser
from langchain_core.outputs import Generation
from langchain_ollama import OllamaLLM

from .utils import get_exclusion_terms


class CustomOutputParser(BaseOutputParser):
    def __init__(self, llm: OllamaLLM, normalization_mode: bool, prompt: str, **kwargs):
        super().__init__()
        self._llm = llm
        self._normalization_mode = normalization_mode
        self._prompt = prompt
        if normalization_mode:
            self._snomed_df = pd.read_csv(
                "./snomed_description_icd_normalized.csv", sep="\t")

    def _check_match(self, diagnostic: str) -> dict[str, str] | None:
        def remove_exclusion_terms(text: str) -> str:
            text_lower = text.lower().strip()
            words = text_lower.split()
            filtered_words = [word for word in words if word not in get_exclusion_terms()]
            return " ".join(filtered_words)
        
        from rapidfuzz import fuzz
        import numpy as np
        
        diagnostic_lower = diagnostic.lower().strip()
        diagnostic_filtered = remove_exclusion_terms(diagnostic_lower)
        
        best_matches = []
        best_scores = []
        
        for column in ['description_es_normalized', 'description_es', 'description_en']:
            if column in self._snomed_df.columns:
                processed_column = self._snomed_df[column].fillna("").str.lower().str.strip().apply(remove_exclusion_terms)
                
                exact_match = self._snomed_df[processed_column == diagnostic_filtered]
                if not exact_match.empty:
                    match_row = exact_match.iloc[0]
                    return {
                        "icd_code": match_row.get('icd_code', ''),
                        "principal_diagnostic": match_row.get('description_es_normalized', diagnostic)
                    }
                
                partial_match_mask = processed_column.str.contains(diagnostic_filtered, regex=False, na=False)
                partial_matches_df = self._snomed_df[partial_match_mask]
                
                if not partial_matches_df.empty:
                    filtered_options = processed_column[partial_match_mask].tolist()
                    indices = np.where(partial_match_mask)[0].tolist()
                    
                    scores = []
                    for option in filtered_options:
                        score = fuzz.token_sort_ratio(diagnostic_filtered, option)
                        scores.append(score)
                    
                    if scores:
                        best_idx = np.argmax(scores)
                        match_idx = indices[best_idx]
                        match_row = self._snomed_df.iloc[match_idx]
                        best_matches.append({
                            "icd_code": match_row.get('icd_code', ''),
                            "principal_diagnostic": match_row.get('description_es_normalized', diagnostic),
                            "source_column": column,
                            "score": scores[best_idx]
                        })
                        best_scores.append(scores[best_idx])
        
        if not best_matches:
            return {
                "icd_code": "N/A",
                "principal_diagnostic": diagnostic
            }
        
        best_idx = np.argmax(best_scores)
        best_match = best_matches[best_idx]
        
        return {
            "icd_code": best_match["icd_code"],
            "principal_diagnostic": best_match["principal_diagnostic"]
        }

    def _generate_icd_code(self, diagnostic: str) -> dict:
        prompt = PromptTemplate.from_template(self._prompt)

        icd_chain = prompt | self._llm | StrOutputParser()

        try:
            icd_code = icd_chain.invoke(
                {"principal_diagnostic": diagnostic})

            # Look for ICD pattern
            icd_match = re.search(r'([A-Z]\d+\.?\d*)', icd_code)

            # Check if a match was found
            if icd_match:
                cleaned_icd = re.sub(r"[\n\r\s]", "", icd_match.group(1))
                return {
                    "icd_code": cleaned_icd,
                    "principal_diagnostic": diagnostic
                }
            else:
                return {
                    "icd_code": "N/A",
                    "principal_diagnostic": diagnostic
                }
        except Exception as e:
            raise Exception(
                f"Error al invocar el modelo para normalizar el diagnóstico: {e}")

    def _clean_reasoning_output(self, text: str) -> str:
        if re.search(r'<think>.*?</think>', text, flags=re.DOTALL | re.IGNORECASE):
            cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
            cleaned_text = re.sub(r'\n\s*\n', '\n\n', cleaned_text)
            return cleaned_text.strip()
        return text

    def parse(self, result: list[Generation], *, partial: bool = False) -> dict:
        try:
            if isinstance(result, list) and result and all(isinstance(x, Generation) for x in result):
                generated_diagnostic = result[0].text.strip()
            elif isinstance(result, Generation):
                generated_diagnostic = result.text.strip()
            elif isinstance(result, str):
                generated_diagnostic = result.strip()
            else:
                generated_diagnostic = str(result).strip()
            generated_diagnostic = self._clean_reasoning_output(generated_diagnostic)
            
            if self._normalization_mode:
                return self._check_match(generated_diagnostic)
            else:
                return self._generate_icd_code(generated_diagnostic)
        except Exception as e:
            raise Exception(
                f"An error ocurred while trying to parse the result: {e}")
