"""
Common utility functions.
"""

import logging
import numpy as np
from typing import Any, Dict, List, Optional, Union
from collections import Counter

logger = logging.getLogger(__name__)


def extract_label(annotation: Dict[str, Any]) -> str:
    """
    Extract label from annotation result.
    
    Args:
        annotation: Annotation dictionary with 'result' key
    
    Returns:
        Extracted label string
    """
    result = annotation.get('result', [])
    
    for item in result:
        value = item.get('value', {})
        
        # Handle choices
        if 'choices' in value:
            choices = value['choices']
            if isinstance(choices, list) and choices:
                return choices[0]
            elif isinstance(choices, dict):
                # Return choice with highest probability
                return max(choices.items(), key=lambda x: x[1])[0]
        
        # Handle labels
        if 'labels' in value:
            labels = value['labels']
            if isinstance(labels, list) and labels:
                return labels[0]
    
    return 'unknown'


def compute_statistics(values: List[Union[int, float]]) -> Dict[str, float]:
    """
    Compute basic statistics for a list of values.
    
    Args:
        values: List of numeric values
    
    Returns:
        Dictionary with statistics
    """
    if not values:
        return {
            'mean': 0.0,
            'std': 0.0,
            'min': 0.0,
            'max': 0.0,
            'median': 0.0,
            'count': 0,
        }
    
    values_array = np.array(values, dtype=float)
    
    return {
        'mean': float(np.mean(values_array)),
        'std': float(np.std(values_array)),
        'min': float(np.min(values_array)),
        'max': float(np.max(values_array)),
        'median': float(np.median(values_array)),
        'count': len(values),
    }


def normalize_scores(scores: Dict[int, float]) -> Dict[int, float]:
    """
    Normalize scores to [0, 1] range.
    
    Args:
        scores: Dictionary mapping id to score
    
    Returns:
        Normalized scores
    """
    if not scores:
        return scores
    
    values = list(scores.values())
    min_val = min(values)
    max_val = max(values)
    
    if max_val == min_val:
        return {k: 0.5 for k in scores}
    
    return {
        k: (v - min_val) / (max_val - min_val)
        for k, v in scores.items()
    }


def compute_label_distribution(annotations: List[Dict]) -> Dict[str, int]:
    """
    Compute label distribution from annotations.
    
    Args:
        annotations: List of annotation dictionaries
    
    Returns:
        Dictionary mapping label to count
    """
    label_counts = Counter()
    
    for annotation in annotations:
        label = extract_label(annotation)
        if label != 'unknown':
            label_counts[label] += 1
    
    return dict(label_counts)


def detect_speed_anomalies(
    annotations: List[Dict],
    threshold: float = 3.0
) -> List[Dict]:
    """
    Detect annotations with anomalous speed.
    
    Args:
        annotations: List of annotations with 'lead_time' field
        threshold: Standard deviation threshold
    
    Returns:
        List of anomalous annotations
    """
    times = []
    valid_annotations = []
    
    for annotation in annotations:
        lead_time = annotation.get('lead_time')
        if lead_time and lead_time > 0:
            times.append(lead_time)
            valid_annotations.append(annotation)
    
    if len(times) < 3:
        return []
    
    mean_time = np.mean(times)
    std_time = np.std(times)
    
    if std_time == 0:
        return []
    
    anomalies = []
    for time, annotation in zip(times, valid_annotations):
        z_score = abs(time - mean_time) / std_time
        if z_score > threshold:
            anomalies.append({
                'annotation': annotation,
                'time': time,
                'z_score': z_score,
                'mean': mean_time,
                'std': std_time,
            })
    
    return anomalies
