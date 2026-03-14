from old_system.utils import color_text
from .data_models import EvaluationResult
import json
from datetime import datetime
from pathlib import Path
import os


class ResultsManager:
    def __init__(self, base_results_dir: Path, single_model_mode: bool):
        self.base_dir = base_results_dir
        self.single_model_mode = single_model_mode
        self.results_dir = self._create_timestamped_results_dir()
        self.summary_data = []
        self.detailed_results = []

    def _create_timestamped_results_dir(self) -> Path:

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        results_dir = self.base_dir / \
            f"{timestamp}_{'individual' if self.single_model_mode else 'multiple'}_evaluation_run"
        results_dir.mkdir(parents=True, exist_ok=True)
        return results_dir

    def add_result(self, result: EvaluationResult) -> None:
        # Add to detailed results
        self.detailed_results.append(result)

        # Extract summary info
        model_name = result.model_info.model_name
        accuracy = result.performance.accuracy
        incorrect = result.performance.incorrect_outputs
        errors = result.performance.errors
        total_texts = result.performance.total_texts
        duration = result.performance.duration
        normalized = result.performance.normalized

        # Create summary entry
        summary_entry = {
            "model_name": model_name,
            "accuracy": accuracy,
            "incorrect_outputs": incorrect,
            "errors": errors,
            "total_texts": total_texts,
            "duration": duration,
            "normalized": normalized,
        }

        self.summary_data.append(summary_entry)

        # Write individual result file
        self._write_individual_result(result)

    def _write_individual_result(self, result: EvaluationResult) -> None:

        model_name = result.model_info.model_name.replace(
            ":", "-").replace("_", "-").replace(".", "-").replace("/","-")
        normalized_tag = "_N" if result.performance.normalized else ""

        # Change saving strategy if execute just for one model
        if self.single_model_mode:
            filename = f"detailed_results_{model_name}{normalized_tag}.json"
            file_path = self.results_dir / filename
        else:
            filename = f"{model_name}{normalized_tag}.json"
            file_path = self.results_dir / "individual_results" / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(exclude_none=True),
                      f, indent=2, ensure_ascii=False)

    def _get_best_model(self) -> dict | None:
        if not self.summary_data:
            return None

        # Sort by accuracy (descending) and return the first one
        sorted_models = sorted(
            self.summary_data, key=lambda x: x["accuracy"], reverse=True)
        return sorted_models[0]

    def generate_comprehensive_report(self) -> None:
        report_path = self.results_dir / "evaluation_report.txt"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("MEDICAL DIAGNOSTIC MODELS EVALUATION REPORT\n")
            f.write(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            f.write("SUMMARY\n")
            f.write("-" * 80 + "\n")

            if self.summary_data:
                best_model = self._get_best_model()

                f.write(f"Total models evaluated: {len(self.summary_data)}\n")
                f.write(
                    f"Best performing model: {best_model['model_name']} (Accuracy: {best_model['accuracy']}%)\n")
                f.write(
                    f"Average accuracy across all models: {sum(m['accuracy'] for m in self.summary_data) / len(self.summary_data):.2f}%\n\n")

                f.write("MODEL COMPARISON\n")
                f.write("-" * 80 + "\n")
                f.write(
                    f"{'Model Name':<30} {'Accuracy':<10} {'Incorrect':<10} {'Errors':<10} {'Duration':<10}\n")
                f.write("-" * 80 + "\n")

                sorted_models = sorted(
                    self.summary_data, key=lambda x: x["accuracy"], reverse=True)

                for model in sorted_models:
                    f.write(
                        f"{model['model_name']:<30} {model['accuracy']:<10.2f} {model['incorrect_outputs']:<10.2f} {model['errors']:<10.2f} {model['duration']:<10.2f}\n")
            else:
                f.write("No models evaluated.\n")

        print(f"\r{' ' * os.get_terminal_size().columns}", end="", flush=True)
        print(f"\r{color_text('COMPLETED')} Processing finished")
