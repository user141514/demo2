from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvalState:
    # Input fields
    report_type: str = ""
    document_text: str = ""
    transcript_text: str = ""
    metadata: dict = field(default_factory=dict)
    user_id: Optional[str] = None
    name: str = ""
    org: str = ""
    score_date: str = ""
    note: str = ""
    pdf_bytes: bytes = b""

    # Extraction
    extraction_error: Optional[str] = None
    transcript_present: bool = False

    # Report definition (loaded during validation)
    definition: dict = field(default_factory=dict)
    error: str = ""  # Fatal validation / processing error

    # Scoring results
    scoring_mode: str = ""
    dimension_results: list = field(default_factory=list)
    total_score: Optional[float] = None
    total_level: str = ""
    overall_comment: str = ""
    strengths: list = field(default_factory=list)
    improvements: list = field(default_factory=list)

    # LLM path
    llm_error: Optional[str] = None
    llm_provider: str = ""
    llm_model: str = ""
    llm_dimensions: list = field(default_factory=list)

    # Confidence (set by compute_confidence)
    confidence: list = field(default_factory=list)
    # Human review gate
    review_required: bool = False
    review_reason: str = ""
    pause_token: Optional[str] = None

    # Assembly
    assembled_result: Optional[dict] = None
    store_error: Optional[str] = None
    upload_path: str = ""

    # Tracing
    _trace: list = field(default_factory=list)
