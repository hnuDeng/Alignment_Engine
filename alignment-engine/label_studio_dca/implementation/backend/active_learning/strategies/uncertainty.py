"""
Active Learning Uncertainty Strategies

Detailed implementations of various uncertainty sampling strategies
for active learning in data-centric AI workflows.

This module provides fine-grained uncertainty estimation methods
that can be used independently or combined in hybrid strategies.
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Union
from scipy import stats
from scipy.special import entr
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class UncertaintyEstimator:
    """
    Comprehensive uncertainty estimation for active learning.
    
    Provides multiple methods for estimating prediction uncertainty,
    including Bayesian approaches, ensemble methods, and calibration.
    """
    
    def __init__(self, method: str = 'ensemble', n_estimators: int = 10):
        """
        Initialize uncertainty estimator.
        
        Args:
            method: Estimation method ('ensemble', 'bayesian', 'calibration')
            n_estimators: Number of estimators for ensemble methods
        """
        self.method = method
        self.n_estimators = n_estimators
        self.models = []
        self.is_fitted = False
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'UncertaintyEstimator':
        """
        Fit the uncertainty estimator.
        
        Args:
            X: Training features
            y: Training labels
        
        Returns:
            Self for chaining
        """
        if self.method == 'ensemble':
            self._fit_ensemble(X, y)
        elif self.method == 'bayesian':
            self._fit_bayesian(X, y)
        elif self.method == 'calibration':
            self._fit_calibration(X, y)
        else:
            raise ValueError(f"Unknown method: {self.method}")
        
        self.is_fitted = True
        return self
    
    def _fit_ensemble(self, X: np.ndarray, y: np.ndarray):
        """Fit ensemble of diverse models."""
        self.models = []
        
        for i in range(self.n_estimators):
            # Create diverse models
            if i % 3 == 0:
                model = RandomForestClassifier(
                    n_estimators=10,
                    max_depth=5,
                    random_state=i
                )
            elif i % 3 == 1:
                model = GradientBoostingClassifier(
                    n_estimators=10,
                    max_depth=3,
                    random_state=i
                )
            else:
                model = MLPClassifier(
                    hidden_layer_sizes=(50,),
                    max_iter=100,
                    random_state=i
                )
            
            # Bootstrap sample
            n_samples = len(X)
            indices = np.random.choice(n_samples, n_samples, replace=True)
            X_boot = X[indices]
            y_boot = y[indices]
            
            model.fit(X_boot, y_boot)
            self.models.append(model)
    
    def _fit_bayesian(self, X: np.ndarray, y: np.ndarray):
        """Fit Bayesian model (simplified using ensemble)."""
        # Simplified Bayesian approach using ensemble
        self._fit_ensemble(X, y)
    
    def _fit_calibration(self, X: np.ndarray, y: np.ndarray):
        """Fit calibrated model."""
        base_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.models = [CalibratedClassifierCV(base_model, cv=3)]
        self.models[0].fit(X, y)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities.
        
        Args:
            X: Features to predict
        
        Returns:
            Probability matrix (n_samples x n_classes)
        """
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before prediction")
        
        if self.method in ['ensemble', 'bayesian']:
            # Average predictions from all models
            all_proba = []
            for model in self.models:
                proba = model.predict_proba(X)
                all_proba.append(proba)
            return np.mean(all_proba, axis=0)
        else:
            return self.models[0].predict_proba(X)
    
    def predict_with_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict with uncertainty estimates.
        
        Args:
            X: Features to predict
        
        Returns:
            Tuple of (predictions, uncertainties)
        """
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before prediction")
        
        if self.method in ['ensemble', 'bayesian']:
            # Get predictions from all models
            all_proba = []
            for model in self.models:
                proba = model.predict_proba(X)
                all_proba.append(proba)
            
            # Average prediction
            avg_proba = np.mean(all_proba, axis=0)
            predictions = np.argmax(avg_proba, axis=1)
            
            # Uncertainty as std across models
            all_proba_array = np.array(all_proba)
            uncertainties = np.std(all_proba_array, axis=0)
            uncertainty_scores = np.mean(uncertainties, axis=1)
            
            return predictions, uncertainty_scores
        else:
            proba = self.models[0].predict_proba(X)
            predictions = np.argmax(proba, axis=1)
            uncertainties = 1.0 - np.max(proba, axis=1)
            return predictions, uncertainties


class BatchUncertaintySampler:
    """
    Batch-mode uncertainty sampling for efficient active learning.
    
    Selects batches of uncertain samples while maintaining diversity
    within the batch.
    """
    
    def __init__(
        self,
        uncertainty_measure: str = 'entropy',
        diversity_weight: float = 0.3,
        batch_size: int = 10
    ):
        """
        Initialize batch sampler.
        
        Args:
            uncertainty_measure: Type of uncertainty measure
            diversity_weight: Weight for diversity in batch selection
            batch_size: Size of batches to select
        """
        self.uncertainty_measure = uncertainty_measure
        self.diversity_weight = diversity_weight
        self.batch_size = batch_size
    
    def compute_uncertainty(self, probabilities: np.ndarray) -> np.ndarray:
        """Compute uncertainty scores."""
        if self.uncertainty_measure == 'entropy':
            probs = np.clip(probabilities, 1e-10, 1.0)
            return -np.sum(probs * np.log(probs), axis=1)
        elif self.uncertainty_measure == 'least_confidence':
            return 1.0 - np.max(probabilities, axis=1)
        elif self.uncertainty_measure == 'margin':
            sorted_probs = np.sort(probabilities, axis=1)[:, ::-1]
            return 1.0 - (sorted_probs[:, 0] - sorted_probs[:, 1])
        else:
            raise ValueError(f"Unknown measure: {self.uncertainty_measure}")
    
    def compute_diversity(self, features: np.ndarray) -> np.ndarray:
        """Compute diversity scores based on feature distances."""
        from scipy.spatial.distance import cdist
        
        # Compute pairwise distances
        distances = cdist(features, features, metric='euclidean')
        
        # Average distance to other samples
        avg_distances = np.mean(distances, axis=1)
        
        # Normalize
        if np.max(avg_distances) > 0:
            return avg_distances / np.max(avg_distances)
        return avg_distances
    
    def select_batch(
        self,
        features: np.ndarray,
        probabilities: np.ndarray,
        batch_size: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Select a diverse batch of uncertain samples.
        
        Args:
            features: Feature matrix
            probabilities: Prediction probabilities
            batch_size: Batch size (overrides default)
        
        Returns:
            Tuple of (selected_indices, scores)
        """
        if batch_size is None:
            batch_size = self.batch_size
        
        batch_size = min(batch_size, len(features))
        
        # Compute uncertainty scores
        uncertainty = self.compute_uncertainty(probabilities)
        
        # Compute diversity scores
        diversity = self.compute_diversity(features)
        
        # Combine scores
        combined = (
            (1 - self.diversity_weight) * uncertainty +
            self.diversity_weight * diversity
        )
        
        # Greedy selection with diversity
        selected = []
        remaining = list(range(len(features)))
        
        for _ in range(batch_size):
            if not remaining:
                break
            
            # Select best remaining
            best_idx = remaining[np.argmax(combined[remaining])]
            selected.append(best_idx)
            remaining.remove(best_idx)
            
            # Update diversity scores to penalize similar samples
            if remaining:
                distances = cdist(
                    features[remaining],
                    features[best_idx:best_idx+1],
                    metric='euclidean'
                )
                # Reduce diversity score for similar samples
                similarity = 1.0 / (1.0 + distances.flatten())
                diversity[remaining] *= (1.0 - similarity * 0.5)
                
                # Recombine
                combined = (
                    (1 - self.diversity_weight) * uncertainty +
                    self.diversity_weight * diversity
                )
        
        return np.array(selected), combined[selected]


class AdaptiveUncertaintyStrategy:
    """
    Adaptive uncertainty strategy that adjusts based on learning progress.
    
    Starts with exploration (diversity) and gradually shifts to
    exploitation (uncertainty) as learning progresses.
    """
    
    def __init__(
        self,
        initial_exploration: float = 0.7,
        final_exploration: float = 0.2,
        decay_rate: float = 0.1
    ):
        """
        Initialize adaptive strategy.
        
        Args:
            initial_exploration: Initial exploration weight
            final_exploration: Final exploration weight
            decay_rate: Rate of exploration decay
        """
        self.initial_exploration = initial_exploration
        self.final_exploration = final_exploration
        self.decay_rate = decay_rate
        self.iteration = 0
    
    def get_exploration_weight(self) -> float:
        """Get current exploration weight."""
        weight = self.initial_exploration * np.exp(-self.decay_rate * self.iteration)
        return max(weight, self.final_exploration)
    
    def update(self):
        """Update iteration counter."""
        self.iteration += 1
    
    def select_samples(
        self,
        features: np.ndarray,
        uncertainties: np.ndarray,
        batch_size: int
    ) -> np.ndarray:
        """
        Select samples using adaptive strategy.
        
        Args:
            features: Feature matrix
            uncertainties: Uncertainty scores
            batch_size: Number of samples to select
        
        Returns:
            Selected indices
        """
        exploration_weight = self.get_exploration_weight()
        
        # Compute diversity
        from scipy.spatial.distance import cdist
        distances = cdist(features, features, metric='euclidean')
        diversity = np.mean(distances, axis=1)
        
        # Normalize
        if np.max(diversity) > 0:
            diversity = diversity / np.max(diversity)
        if np.max(uncertainties) > 0:
            uncertainties = uncertainties / np.max(uncertainties)
        
        # Combine
        scores = (
            (1 - exploration_weight) * uncertainties +
            exploration_weight * diversity
        )
        
        # Select top-k
        selected = np.argsort(scores)[-batch_size:][::-1]
        
        self.update()
        
        return selected
