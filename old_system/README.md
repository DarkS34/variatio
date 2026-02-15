# Medical Evolution Text Analyzer

> ⚠️ **Important Notice for Normalization Mode**  
> To enable SNOMED-CT normalization mode (`-N` flag), users must first register on the Spanish SNOMED-CT licensing platform:  
> https://snomed-ct.sanidad.gob.es/snomed-ct/solicitudLicencia.do  
>  
> After obtaining access, download the required datasets as specified at the beginning of the script `create_snomed_normalized_icd_dataset.py`.  
> These include the Spanish and International SNOMED-CT description files and the ExtendedMapSnapshot. The filenames and exact paths are provided within the script.

![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen)

A sophisticated tool for extracting and normalizing rheumatologic diagnoses from Spanish clinical evolution texts using local LLMs and SNOMED-CT mappings.

## Table of Contents

* [Overview](#overview)
* [Features](#features)
* [Requirements](#requirements)
* [Installation](#installation)
* [Usage](#usage)

  * [Command Line Arguments](#command-line-arguments)
  * [Execution Examples](#execution-examples)
* [Architecture](#architecture)
* [Processing Flow](#processing-flow)
* [Directory Structure](#directory-structure)
* [Data Format](#data-format)
* [Results](#results)



## Overview

**Medical Evolution Text Analyzer** processes Spanish-language clinical evolution notes to extract principal rheumatologic diagnoses and corresponding ICD-10 codes. It leverages local language models via the Ollama API and integrates a SNOMED-CT-based normalization module to enhance diagnosis consistency.

## Features

* Summarizes long clinical notes to fit context windows
* Extracts principal rheumatologic diagnoses using strict prompt engineering
* Maps diagnoses to ICD-10 codes through direct or SNOMED-enhanced logic
* Applies fuzzy and keyword-based validation of results
* Evaluates multiple LLMs in parallel
* Provides performance metrics and result visualizations
* Command-line driven with multiple modes and settings

## Requirements

* Python 3.10+
* [Ollama](https://ollama.ai/) running locally
* SNOMED-CT and ICD datasets (included in the repository)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/username/evolution-text-analysis.git
cd evolution-text-analysis
```

2. Install `uv` package manager (recommended). More information at [UV installing web](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_2):

```bash
pip install uv
```

3. Install dependencies using `uv`:

```bash
uv sync
```

4. Ensure Ollama is running:

```bash
https://ollama.com/download
```

> ⚠️ No need to manually prepare SNOMED-CT files — a normalized version is bundled and ready to use.

## Usage

```bash
uv run main.py [options]
```

### Command Line Arguments

| Argument                 | Description                                         |
| ------------------------ | --------------------------------------------------- |
| `-f`, `--filename`       | File with evolution texts (`.csv` or `.json`)       |
| `-m`, `--mode`           | Test mode: `1` (all models), `2` (manual selection) |
| `-b`, `--batches`        | Number of texts per processing batch                |
| `-n`, `--num-texts`      | Max number of texts to process                      |
| `-W`, `--context-window` | Max token context window size                       |
| `-t`, `--test`           | Enable test mode for evaluation                     |
| `-i`, `--installed`      | Only use installed models                           |
| `-v`, `--verbose`        | Print detailed processing info                      |
| `-N`, `--normalize`      | Use SNOMED-CT for ICD normalization                 |

### Execution Examples

```bash
# Analyze with default config (optimal model)
uv run main.py

# Evaluate all installed models
uv run main.py -tiv

# Evaluate one selected model with SNOMED normalization
uv run main.py -tN -m2

# Analyze 50 records in 4 parallel batches
uv run main.py -n50 -b4
```

## Architecture

* `main.py`: Entry point handling CLI and mode selection
* `analyzer.py`: Analysis engine combining LLM, summarizer, and parser
* `tester.py`: Model evaluation framework with metrics and reporting
* `_custom_output_parser.py`: ICD mapping and SNOMED normalization logic
* `_validator.py`: Rule-based and fuzzy diagnosis validation
* `utils.py`: Argument parsing, file I/O, summarization helper
* `data_models.py`: Pydantic schemas for all structured objects

## Processing Flow

1. **Startup**

   * Verify Ollama is running
   * Load config and evolution text data

2. **Text Preprocessing**

   * Optionally summarize long records to fit context window

3. **Diagnosis Extraction**

   * LLM returns a single-line principal diagnosis

4. **ICD Code Assignment**

   * Model or SNOMED-CT-driven mapping logic

5. **Normalization & Validation** (if enabled)

   * Filter, expand, and fuzzy match diagnostics

6. **Result Handling**

   * Save per-record results as JSON
   * Compute accuracy and error metrics
   * Generate optional charts (for test mode)

## Directory Structure

```
.
├── evolution_text_analyzer/
│   ├── __init__.py
│   ├── analyzer.py
│   ├── tester.py
│   ├── _custom_output_parser.py
│   ├── _validator.py
│   ├── utils.py
│   ├── data_models.py
├── main.py
├── config.json
├── create_snomed_normalized_icd_dataset.py
├── snomed_description_icd_normalized.csv
├── results/
├── testing_results/
└── pyproject.toml
```

## Data Format

### Input

CSV or JSON file with fields:

* `id`: Unique record ID
* `evolution_text`: Raw clinical text (Spanish)
* `principal_diagnostic`: Ground-truth diagnosis (only for test mode)

### Config (JSON)

```json
{
  "optimal_model": 0,
  "models": ["model1", "model2", ...],
  "prompts": {
    "gen_summary_prompt": "...",
    "gen_diagnostic_prompt": "...",
    "gen_icd_code_prompt": "..."
  }
}
```

## Results

* Saved in `results/` (normal mode) or `testing_results/` (test mode)
* Includes JSON with model outputs, performance metrics, and optional charts

---

For issues or contributions, please open a GitHub issue or PR.
