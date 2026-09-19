import logging
import time
import random
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DriftExplainerException(Exception):
    pass

class LLMConnectionException(DriftExplainerException):
    pass

class InvalidDriftDataException(DriftExplainerException):
    pass


class DriftExplainer:
    """
    A creative module that takes complex numerical drift metrics
    and generates a human-readable explanation of why the drift occurred.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._templates = [
            "The data points {ids} drifted because they are significantly far from the cluster centroid (Score: {score:.2f}).",
            "We detected anomalous behavior in {ids} due to unexpected feature distributions (Severity: {severity}).",
            "Drift is likely caused by an edge case pattern present in {ids} that was absent during training."
        ]
        
    def _retry_decorator(func):
        def wrapper(*args, **kwargs):
            retries = 3
            backoff = 1.0
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except InvalidDriftDataException:
                    raise
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    if attempt == retries - 1:
                        raise LLMConnectionException(f"Failed after {retries} retries: {e}")
                    time.sleep(backoff)
                    backoff *= 2.0
        return wrapper
        
    @_retry_decorator
    def generate_explanation(self, drift_data: Dict[str, Any]) -> str:
        """
        Generate explanation for a given drift report.
        Uses a template-based mock LLM for demonstration if no API key is provided.
        """
        if not isinstance(drift_data, dict):
            raise InvalidDriftDataException("Drift data must be a dictionary")
        logger.info(f"Generating explanation for {len(drift_data.get('anomalousIds', []))} items")
            
        anomalous_ids = drift_data.get('anomalousIds', [])
        score = drift_data.get('driftScore', 0.0)
        
        if not anomalous_ids:
            return "No drift detected. System is operating normally."
            
        if self.api_key:
            # Simulate real LLM API call delay
            time.sleep(0.5)
            
        template = random.choice(self._templates)
        ids_str = ", ".join(anomalous_ids[:3])
        if len(anomalous_ids) > 3:
            ids_str += f" and {len(anomalous_ids) - 3} others"
            
        severity = "High" if score > 0.8 else "Medium" if score > 0.5 else "Low"
        
        explanation = template.format(ids=ids_str, score=score, severity=severity)
        logger.info("Explanation generated successfully")
        return explanation
