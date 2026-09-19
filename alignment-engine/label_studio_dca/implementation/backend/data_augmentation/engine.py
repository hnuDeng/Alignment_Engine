"""
Augmentation engine that coordinates augmenters.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.data_augmentation.augmenters import (
    BaseAugmenter,
    TextAugmenter,
    NumericAugmenter,
    CategoricalAugmenter,
)

logger = logging.getLogger(__name__)


class AugmentationEngine:
    """
    Engine for data augmentation.
    
    Coordinates multiple augmenters to generate synthetic data.
    """
    
    def __init__(self):
        """Initialize augmentation engine."""
        self.augmenters: Dict[str, BaseAugmenter] = {
            'text': TextAugmenter(),
            'numeric': NumericAugmenter(),
            'categorical': CategoricalAugmenter(),
        }
    
    def augment_batch(
        self,
        data_list: List[Dict[str, Any]],
        num_augmented_per_item: int = 1,
        augmenter_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Augment a batch of data.
        
        Args:
            data_list: List of original data
            num_augmented_per_item: Number of augmented samples per original item
            augmenter_type: Type of augmenter to use (None for auto-detect)
        
        Returns:
            List of augmented data
        """
        augmented_data = []
        
        for data in data_list:
            # Auto-detect augmenter type
            if augmenter_type is None:
                augmenter_type = self._detect_type(data)
            
            augmenter = self.augmenters.get(augmenter_type)
            if augmenter:
                samples = augmenter.augment(data, num_augmented_per_item)
                augmented_data.extend(samples)
            else:
                logger.warning(f'Unknown augmenter type: {augmenter_type}')
                augmented_data.append(data)
        
        return augmented_data
    
    def _detect_type(self, data: Dict[str, Any]) -> str:
        """
        Detect the type of data for augmentation.
        
        Args:
            data: Data dictionary
        
        Returns:
            Augmenter type
        """
        has_text = False
        has_numeric = False
        
        for value in data.values():
            if isinstance(value, str) and len(value) > 10:
                has_text = True
            elif isinstance(value, (int, float)):
                has_numeric = True
        
        if has_text:
            return 'text'
        elif has_numeric:
            return 'numeric'
        else:
            return 'categorical'
