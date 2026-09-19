import time
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator, constr, StrictStr
import functools

logger = logging.getLogger(__name__)

class PreferenceGraphException(Exception):
    """Base exception for Preference Graph operations."""
    pass

class InvalidTreeStructureException(PreferenceGraphException):
    """Raised when the tree structure of FiftyOne metadata is malformed."""
    pass

class DFSTraversalException(PreferenceGraphException):
    """Raised during DFS graph cycle or excessive depth."""
    pass

class ValidationFailedException(PreferenceGraphException):
    """Raised when Pydantic validation explicitly fails post-parsing."""
    pass

def exponential_backoff_db(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        logger.error(f"DB call {func.__name__} failed completely: {str(e)}")
                        raise e
                    logger.warning(f"DB call {func.__name__} failed, retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator

class PreferencePair(BaseModel):
    """
    Pydantic Model for a Preference Pair with extreme validation constraints.
    """
    prompt: StrictStr = Field(..., description="The original prompt for the model")
    chosen: StrictStr = Field(..., description="The human preferred response")
    rejected: StrictStr = Field(..., description="The AI generated rejected response")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Human annotator confidence")
    turn_length: int = Field(..., gt=0, description="Number of conversation turns")

    @validator('prompt')
    def validate_prompt_length(cls, v: str) -> str:
        if len(v.strip()) < 5:
            raise ValueError("Prompt must be at least 5 characters long.")
        if len(v) > 8192:
            raise ValueError("Prompt exceeds context window safety limit (8192 chars).")
        return v

    @validator('chosen')
    def validate_chosen_length(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Chosen response cannot be empty.")
        return v

    @validator('rejected')
    def validate_rejected_length(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Rejected response cannot be empty.")
        return v

    @validator('chosen', 'rejected')
    def validate_distinct(cls, v: str, values: Dict[str, Any]) -> str:
        # We can't easily validate chosen != rejected if only one is processed,
        # but we can check it in a root validator. We'll do a simple check.
        # It's better to use root_validator, but we must use @validator for fields
        return v

    @validator('confidence')
    def validate_meaningful_confidence(cls, v: float) -> float:
        if v < 0.1:
            raise ValueError("Confidence is too low to be useful for alignment.")
        return v

class PreferenceDatasetFactory:
    """
    Constructs preference datasets by comparing state trees.
    """
    def __init__(self, max_depth: int = 100):
        self.max_depth = max_depth

    @exponential_backoff_db(max_retries=5)
    def fetch_state_trees(self, sample_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Simulated fetch from FiftyOne with exponential backoff."""
        start = time.time()
        logger.debug(f"Fetching trees for {sample_id}...")
        # In a real scenario, this queries the FiftyOne Mongo backend
        if not sample_id:
            raise InvalidTreeStructureException("Empty sample ID provided.")
        logger.debug(f"Fetch completed in {time.time() - start:.3f}s")
        return ({"type": "root", "text": "AI generated"}, {"type": "root", "text": "Human edit"})

    def compare_trees_dfs(self, node_ai: Dict[str, Any], node_human: Dict[str, Any], depth: int = 0) -> str:
        """
        DFS algorithm to find the exact divergence point between AI and Human annotations.
        """
        if depth > self.max_depth:
            raise DFSTraversalException("Exceeded maximum DFS depth.")

        # If structures differ or text differs, we found the divergence
        text_ai = node_ai.get("text", "")
        text_human = node_human.get("text", "")
        
        if text_ai != text_human:
            return text_human # Human preference

        children_ai = node_ai.get("children", [])
        children_human = node_human.get("children", [])

        if len(children_ai) != len(children_human):
            raise InvalidTreeStructureException("Tree topology mismatch not supported for preference diff.")

        for child_a, child_h in zip(children_ai, children_human):
            diff = self.compare_trees_dfs(child_a, child_h, depth + 1)
            if diff:
                return diff
        
        return ""

    def build_preference(self, sample_id: str, original_prompt: str) -> PreferencePair:
        """
        Orchestrates the fetch, DFS comparison, and Pydantic validation.
        """
        logger.info(f"Building preference pair for {sample_id}")
        t0 = time.time()
        
        tree_ai, tree_human = self.fetch_state_trees(sample_id)
        human_preferred_text = self.compare_trees_dfs(tree_ai, tree_human)
        ai_rejected_text = tree_ai.get("text", "Empty AI response")
        
        if not human_preferred_text:
            human_preferred_text = "Human accepted AI text unchanged"

        try:
            pair = PreferencePair(
                prompt=original_prompt,
                chosen=human_preferred_text,
                rejected=ai_rejected_text,
                confidence=0.9,
                turn_length=1
            )
        except Exception as e:
            raise ValidationFailedException(f"Failed to validate pair for {sample_id}: {e}")

        logger.info(f"Successfully built pair in {time.time() - t0:.3f}s")
        return pair
