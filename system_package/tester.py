import time
from pathlib import Path

from ._validator import Validator
from .analyzer import Analyzer
from .data_models import (
    DiagnosticResult,
    EvaluationOutput,
    EvaluationResult,
    ModelInfo,
    PerformanceMetrics,
)
from .results_manager import ResultsManager
from .utils import (
    choose_model,
    get_listed_models_info,
    model_installed,
    print_evaluated_results,
)


class AnalyzerTester():
    def __init__(self, models_names: list[str],
                 prompts: dict,
                 evolution_texts: list[dict],
                 testing_results_dir: Path,
                 args,
                 date_format: str = "%H:%M:%S %d-%m-%Y"
                 ):
        self.models = models_names
        self.prompts = prompts
        self.evolution_texts = evolution_texts
        self.testing_results_dir = testing_results_dir
        self.args = args
        self.date_format = date_format
        self.validator = Validator()
        self.results_manager = ResultsManager(
            testing_results_dir, args.eval_mode == 2)

    def _validate_result(self, generated_diagnostic: dict, correct_diagnostic: str) -> EvaluationOutput:
        try:
            if not generated_diagnostic.get("processing_error"):
                valid = self.validator.validate(generated_diagnostic.get(
                    "principal_diagnostic"), correct_diagnostic)
            else:
                valid = False
            result = DiagnosticResult(
                icd_code=generated_diagnostic.get("icd_code"),
                principal_diagnostic=generated_diagnostic.get(
                    "principal_diagnostic"),
                processing_error=generated_diagnostic.get("processing_error"),
            )
        except Exception as e:
            valid = False
            result = DiagnosticResult(
                icd_code=None,
                principal_diagnostic=None,
                validation_error=str(e),
            )

        return EvaluationOutput(
            valid=valid,
            processed_output=result,
            summarized=generated_diagnostic.get("summarized"),
            correct_diagnostic=correct_diagnostic
        )

    def _calculate_metrics(self,
                           evaluated: dict[str, EvaluationOutput],
                           total_texts: int,
                           num_batches: int,
                           start: float,
                           end: float,
                           normalized: bool,
                           ) -> PerformanceMetrics:

        valid = sum(1 for e in evaluated.values() if e.valid)
        errors = sum(
            1 for e in evaluated.values()
            if not e.valid and (e.processed_output.validation_error or e.processed_output.processing_error)
        )
        incorrect = total_texts - valid - errors

        return PerformanceMetrics(
            accuracy=round((valid / total_texts) * 100, 2),
            incorrect_outputs=round((incorrect / total_texts) * 100, 2),
            errors=round((errors / total_texts) * 100, 2),
            hits=valid,
            total_texts=total_texts,
            duration=round(end - start, 2),
            start_time=time.strftime(self.date_format, time.localtime(start)),
            end_time=time.strftime(self.date_format, time.localtime(end)),
            num_batches=num_batches,
            normalized=normalized,
        )

    def _evaluate_model(self, analyzer: Analyzer, model_info: ModelInfo) -> EvaluationResult:

        start = time.time()
        generated_diagnostics = analyzer.analyze(self.evolution_texts)
        end = time.time()
        
        evaluated = {
            key: self._validate_result(generated_diagnostic, self.evolution_texts[i]["principal_diagnostic"])
            for i, (key, generated_diagnostic) in enumerate(generated_diagnostics.items())
        }

        metrics = self._calculate_metrics(
            evaluated,
            total_texts=self.args.num_texts,
            num_batches=self.args.process_batch,
            start=start,
            end=end,
            normalized=self.args.normalization_mode,
        )

        return EvaluationResult(
            model_info=model_info,
            performance=metrics,
            evaluated_texts=evaluated
        )

    def evaluate_analysis(self):
        if self.args.eval_mode == 1 and len(self.models) > 1:
            models_info = get_listed_models_info(
                self.models, self.args.only_installed_models_mode)

            for model_info in models_info:
                if model_installed(model_info.model_name):
                    analyzer = Analyzer(model_info.model_name,
                                        self.prompts,
                                        self.args.process_batch,
                                        self.args.num_texts,
                                        self.args.normalization_mode,
                                        self.args.selected_context_window,
                                        True)

                    evaluation_result = self._evaluate_model(
                        analyzer, model_info)

                    self.results_manager.add_result(evaluation_result)

            self.results_manager.generate_comprehensive_report()

        # Single model evaluation
        elif self.args.eval_mode == 2 or len(self.models) == 1:

            model_info = choose_model(
                self.models, self.args.only_installed_models_mode)

            analyzer = Analyzer(model_info.model_name,
                                self.prompts,
                                self.args.process_batch,
                                self.args.num_texts,
                                self.args.normalization_mode,
                                self.args.selected_context_window,
                                True)

            evaluation_result = self._evaluate_model(analyzer, model_info)

            self.results_manager.add_result(evaluation_result)

            print_evaluated_results(
                model_info, evaluation_result, self.args.verbose_mode)
