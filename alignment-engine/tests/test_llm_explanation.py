import pytest
from core.creative.llm_explanation import DriftExplainer, InvalidDriftDataException

def test_drift_explainer_no_drift():
    explainer = DriftExplainer()
    explanation = explainer.generate_explanation({"anomalousIds": [], "driftScore": 0.0})
    assert explanation == "No drift detected. System is operating normally."

def test_drift_explainer_with_drift():
    explainer = DriftExplainer()
    explanation = explainer.generate_explanation({"anomalousIds": ["id1", "id2"], "driftScore": 0.9})
    assert "id1, id2" in explanation

def test_drift_explainer_invalid_data():
    explainer = DriftExplainer()
    with pytest.raises(InvalidDriftDataException):
        explainer.generate_explanation(["invalid", "data"])
