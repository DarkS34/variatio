from pathlib import Path

from system_package.analyzer import Analyzer
from system_package.utils import (
    check_ollama_connection,
    get_analyzer_configuration,
    get_args,
    get_evolution_texts,
    model_installed,
    write_results,
)

from system_package.tester import AnalyzerTester


def run_test_analysis_mode(models_names: list[str], evolution_texts, prompts: dict, args) -> None:

    testing_results_dir = config_file.parent / "testing" / "results"
    testing_results_dir.mkdir(parents=True, exist_ok=True)

    args.num_texts = args.num_texts if args.num_texts is not None else len(
        evolution_texts)

    tester = AnalyzerTester(models_names,
                            prompts,
                            evolution_texts,
                            testing_results_dir,
                            args)

    tester.evaluate_analysis()


def run_analysis_mode(model_name: str, evolution_texts, prompts: dict, args) -> None:

    args.num_texts = args.num_texts if args.num_texts is not None and args.num_texts > 0 else len(
        evolution_texts)

    results_dir = config_file.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    analyzer = Analyzer(prompts,
                        evolution_texts,
                        args.process_batch,
                        args.num_texts,
                        args.normalization_mode,
                        args.selected_context_window
                        )

    results = analyzer.analyze(model_name)

    write_results(results_dir / "processed_evolution_texts.json", results)


if __name__ == "__main__":
    check_ollama_connection()

    base_path = Path(__file__).parent
    config_file = base_path / "config.json"

    config = get_analyzer_configuration(config_file)
    opt_model, models = config["optimal_model"], config["models"]

    args = get_args()
    evolution_texts = get_evolution_texts(base_path / args.et_filename)

    
    
    if args.test_mode:
        run_test_analysis_mode(models, evolution_texts,
                               config["prompts"], args)
    else:
        model_name = models[opt_model]
        if model_installed(model_name):
            run_analysis_mode(model_name, evolution_texts,
                              config["prompts"], args)
