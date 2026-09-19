"""
Data augmenters for different data types.
"""

import logging
import random
import string
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class BaseAugmenter(ABC):
    """Base class for data augmenters."""
    
    @abstractmethod
    def augment(self, data: Dict[str, Any], num_samples: int = 1) -> List[Dict[str, Any]]:
        """
        Augment data.
        
        Args:
            data: Original data
            num_samples: Number of augmented samples to generate
        
        Returns:
            List of augmented data samples
        """
        raise NotImplementedError


class TextAugmenter(BaseAugmenter):
    """Text data augmenter."""
    
    def __init__(
        self,
        synonym_replacement: bool = True,
        random_insertion: bool = False,
        random_swap: bool = True,
        random_deletion: bool = False,
    ):
        """
        Initialize text augmenter.
        
        Args:
            synonym_replacement: Whether to replace words with synonyms
            random_insertion: Whether to insert random words
            random_swap: Whether to swap random words
            random_deletion: Whether to delete random words
        """
        self.synonym_replacement = synonym_replacement
        self.random_insertion = random_insertion
        self.random_swap = random_swap
        self.random_deletion = random_deletion
    
    def augment(self, data: Dict[str, Any], num_samples: int = 1) -> List[Dict[str, Any]]:
        """
        Augment text data.
        
        Args:
            data: Original data with 'text' field
            num_samples: Number of augmented samples
        
        Returns:
            List of augmented data samples
        """
        results = []
        
        for _ in range(num_samples):
            augmented = data.copy()
            
            # Find text fields
            for key, value in data.items():
                if isinstance(value, str):
                    augmented[key] = self._augment_text(value)
            
            results.append(augmented)
        
        return results
    
    def _augment_text(self, text: str) -> str:
        """Augment a single text string."""
        words = text.split()
        
        if not words:
            return text
        
        # Random swap
        if self.random_swap and len(words) > 1:
            idx1, idx2 = random.sample(range(len(words)), 2)
            words[idx1], words[idx2] = words[idx2], words[idx1]
        
        # Random deletion
        if self.random_deletion and len(words) > 3:
            idx = random.randint(0, len(words) - 1)
            words.pop(idx)
        
        return ' '.join(words)


class NumericAugmenter(BaseAugmenter):
    """Numeric data augmenter."""
    
    def __init__(
        self,
        noise_std: float = 0.1,
        scale_range: tuple = (0.9, 1.1),
    ):
        """
        Initialize numeric augmenter.
        
        Args:
            noise_std: Standard deviation of noise
            scale_range: Range for random scaling
        """
        self.noise_std = noise_std
        self.scale_range = scale_range
    
    def augment(self, data: Dict[str, Any], num_samples: int = 1) -> List[Dict[str, Any]]:
        """
        Augment numeric data.
        
        Args:
            data: Original data with numeric fields
            num_samples: Number of augmented samples
        
        Returns:
            List of augmented data samples
        """
        results = []
        
        for _ in range(num_samples):
            augmented = data.copy()
            
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    # Add noise
                    noise = np.random.normal(0, self.noise_std)
                    scale = np.random.uniform(*self.scale_range)
                    augmented[key] = float(value * scale + noise)
            
            results.append(augmented)
        
        return results


class CategoricalAugmenter(BaseAugmenter):
    """Categorical data augmenter."""
    
    def __init__(
        self,
        flip_probability: float = 0.1,
        categories: Optional[Dict[str, List[str]]] = None,
    ):
        """
        Initialize categorical augmenter.
        
        Args:
            flip_probability: Probability of flipping a category
            categories: Dictionary mapping field names to possible categories
        """
        self.flip_probability = flip_probability
        self.categories = categories or {}
    
    def augment(self, data: Dict[str, Any], num_samples: int = 1) -> List[Dict[str, Any]]:
        """
        Augment categorical data.
        
        Args:
            data: Original data with categorical fields
            num_samples: Number of augmented samples
        
        Returns:
            List of augmented data samples
        """
        results = []
        
        for _ in range(num_samples):
            augmented = data.copy()
            
            for key, value in data.items():
                if key in self.categories and random.random() < self.flip_probability:
                    # Flip to a different category
                    possible_values = [v for v in self.categories[key] if v != value]
                    if possible_values:
                        augmented[key] = random.choice(possible_values)
            
            results.append(augmented)
        
        return results
