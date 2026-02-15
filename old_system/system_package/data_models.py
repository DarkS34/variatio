from typing import Dict, Optional
from pydantic import BaseModel, Field


class DiagnosticResult(BaseModel):
    icd_code: Optional[str] = Field(
        description="The extracted ICD code for the diagnosis"
    )
    principal_diagnostic: Optional[str] = Field(
        description="The extracted principal diagnosis text"
    )
    validation_error: Optional[str] = Field(
        None, description="Error encountered during validation, if any"
    )
    processing_error: Optional[str] = Field(
        None, description="Error encountered during processing, if any"
    )


class EvaluationOutput(BaseModel):
    valid: bool = Field(
        description="Whether the processed output matches the correct diagnosis"
    )
    summarized: bool = Field(
        description="Wheter the evolution text has been summarized prior of the processing")
    processed_output: DiagnosticResult = Field(
        description="The processed diagnostic result from the model"
    )
    correct_diagnostic: str = Field(
        description="The correct reference diagnosis for comparison"
    )


class PerformanceMetrics(BaseModel):
    accuracy: float = Field(
        description="Percentage of correctly identified diagnoses"
    )
    incorrect_outputs: float = Field(
        description="Percentage of incorrect diagnoses"
    )
    errors: float = Field(
        description="Percentage of processing or validation errors"
    )
    hits: int = Field(
        description="Number of correctly identified diagnoses"
    )
    total_texts: int = Field(
        description="Total number of texts processed"
    )
    duration: float = Field(
        description="Total processing time in seconds"
    )
    start_time: str = Field(
        description="Start time of the evaluation"
    )
    end_time: str = Field(
        description="End time of the evaluation"
    )
    num_batches: int = Field(
        description="Number of batches used for processing"
    )
    normalized: bool = Field(
        description="Whether diagnosis normalization was applied"
    )


class ModelInfo(BaseModel):
    model_name: str = Field(
        description="Name of the model"
    )
    installed: bool = Field(
        False, description="Whether the model is installed locally"
    )
    size: Optional[str] = Field(
        None, description="Size of the model in GB"
    )
    parameter_size: Optional[str] = Field(
        None, description="Number of parameters in the model"
    )
    quantization_level: Optional[str] = Field(
        None, description="Level of quantization applied to the model"
    )


class EvaluationResult(BaseModel):
    model_info: ModelInfo = Field(
        description="Information about the evaluated model"
    )
    performance: PerformanceMetrics = Field(
        description="Performance metrics for the evaluation"
    )
    evaluated_texts: Dict[str, EvaluationOutput] = Field(
        description="Detailed results for each processed text"
    )


class SummarizerConfig(BaseModel):
    chunk_size: int = Field(
        default=1024, description="Size of each chunk in characters")
    chunk_overlap: int = Field(
        default=128, description="Overlap between chunks")
    separator: str = Field(
        default=".", description="Text separator for chunks")
    tokens_per_word: float = Field(
        default=1.3, description="Estimated tokens per word")
    safety_margin: int = Field(
        default=800, description="Safety margin for context window")
