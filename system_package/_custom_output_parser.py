import re

import pandas as pd
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.outputs import Generation
from langchain_ollama import OllamaLLM


class CustomOutputParser(BaseOutputParser):
    def __init__(self, llm: OllamaLLM, normalization_mode: bool, prompt: str, **kwargs):
        super().__init__()
        self._llm = llm
        self._normalization_mode = normalization_mode
        self._prompt = prompt
        if normalization_mode:
            self._snomed_df = pd.read_csv(
                "./snomed_description_icd_normalized.csv", sep="\t")



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
            
            
            
        except Exception as e:
            raise Exception(
                f"An error ocurred while trying to parse the result: {e}")
