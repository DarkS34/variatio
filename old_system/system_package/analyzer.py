from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_ollama.llms import OllamaLLM

from ._custom_output_parser import CustomOutputParser
from .utils import get_context_window_length, print_execution_progression, EvolutionTextSummarizer


class Analyzer():
    def __init__(self,
                 model_name,
                 prompts,
                 process_batch,
                 limit_num_texts,
                 normalization_mode,
                 selected_context_window,
                 test_mode=False):

        self.model_name = model_name

        self.context_window_length = get_context_window_length(
            model_name, selected_context_window)

        self.model = OllamaLLM(
            model=model_name,
            temperature=0,
            num_ctx=self.context_window_length
        )

        self.summarizer = EvolutionTextSummarizer(
            self.model, prompts["gen_summary_prompt"], self.context_window_length)

        self.diagnosis_prompt = PromptTemplate.from_template(
            prompts["gen_diagnostic_prompt"])

        self.parser = CustomOutputParser(
            self.model, normalization_mode, prompts["gen_icd_code_prompt"])

        # Diagnosis chain
        self.diagnosis_chain = self.diagnosis_prompt | self.model | self.parser
        self.process_batch = process_batch
        self.limit_num_texts = limit_num_texts
        self.test_mode = test_mode

    def process_evolution_text(self, evolution_text: str):
        try:
            processed_text = evolution_text
            result = dict()

            if self.summarizer.needs_summarization(evolution_text):
                processed_text = self.summarizer.summarize_text(evolution_text)
                if self.test_mode:
                    result.update({"summarized": True})
            else:
                if self.test_mode:
                    result.update({"summarized": False})

            result.update(self.diagnosis_chain.invoke(
                {"evolution_text": processed_text}))

            return result
        except Exception as e:
            return {
                "principal_diagnostic": None,
                "icd_code": None,
                "summarized": False,
                "processing_error": str(e),
            }

    def analyze(
        self,
        evolution_texts
    ):
        process_batch = min(self.process_batch, len(evolution_texts))
        limit_num_texts = min(self.limit_num_texts, len(evolution_texts))

        processed_evolution_texts = dict()

        for start in range(0, limit_num_texts, process_batch):
            # Print progress once before processing
            print_execution_progression(
                self.model_name,
                len(processed_evolution_texts),
                self.limit_num_texts,
                self.test_mode
            )

            batch = evolution_texts[start: start + self.process_batch]

            # Simplified parallel runner creation
            parallel_runner = RunnableParallel(
                {
                    str(item["id"]): RunnableLambda(
                        lambda x, i=i: self.process_evolution_text(
                            x[i]["evolution_text"]
                        )
                    )
                    for i, item in enumerate(batch)
                }
            )

            processed_evolution_texts.update(parallel_runner.invoke(batch))

        return processed_evolution_texts
