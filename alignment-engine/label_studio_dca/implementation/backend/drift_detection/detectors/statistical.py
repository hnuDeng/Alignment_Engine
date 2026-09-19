"""
Drift Detection Module

Comprehensive data and concept drift detection system for monitoring
changes in data distributions and model performance over time.

Implements multiple drift detection methods:
- Statistical tests (KS test, Chi-square, PSI)
- Distance-based methods (Wasserstein, MMD)
- Model-based methods (classifier drift detection)
- Sequential methods (ADWIN, Page-Hinkley)
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from scipy import stats
from scipy.spatial.distance import cdist
from collections import deque
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class DriftType(Enum):
    """Types of drift that can be detected."""
    DATA_DRIFT = "data_drift"
    CONCEPT_DRIFT = "concept_drift"
    LABEL_DRIFT = "label_drift"
    FEATURE_DRIFT = "feature_drift"


class DriftSeverity(Enum):
    """Severity levels for detected drift."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftDetectionResult:
    """Result of a drift detection analysis."""
    drift_detected: bool
    drift_type: DriftType
    severity: DriftSeverity
    score: float  # 0.0 to 1.0
    p_value: Optional[float]
    statistic: float
    details: Dict[str, Any]
    timestamp: float
    window_size: int


@dataclass
class DriftAlert:
    """Alert generated when drift is detected."""
    alert_id: str
    drift_type: DriftType
    severity: DriftSeverity
    message: str
    details: Dict[str, Any]
    timestamp: float
    acknowledged: bool = False


class StatisticalDriftDetector:
    """
    Statistical drift detection using hypothesis testing.
    
    Implements multiple statistical tests for detecting distribution changes:
    - Kolmogorov-Smirnov test (continuous features)
    - Chi-square test (categorical features)
    - Population Stability Index (PSI)
    - Jensen-Shannon divergence
    """
    
    def __init__(self, significance_level: float = 0.05):
        """
        Initialize statistical detector.
        
        Args:
            significance_level: Significance level for hypothesis tests
        """
        self.significance_level = significance_level
    
    def ks_test(
        self,
        reference: np.ndarray,
        current: np.ndarray
    ) -> Tuple[float, float]:
        """
        Kolmogorov-Smirnov test for continuous distributions.
        
        Args:
            reference: Reference distribution
            current: Current distribution
        
        Returns:
            Tuple of (statistic, p_value)
        """
        if len(reference) == 0 or len(current) == 0:
            return 0.0, 1.0
        
        statistic, p_value = stats.ks_2samp(reference, current)
        return float(statistic), float(p_value)
    
    def chi_square_test(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        n_bins: int = 10
    ) -> Tuple[float, float]:
        """
        Chi-square test for categorical distributions.
        
        Args:
            reference: Reference distribution
            current: Current distribution
            n_bins: Number of bins for discretization
        
        Returns:
            Tuple of (statistic, p_value)
        """
        if len(reference) == 0 or len(current) == 0:
            return 0.0, 1.0
        
        # Create bins
        all_values = np.concatenate([reference, current])
        bins = np.linspace(np.min(all_values), np.max(all_values), n_bins + 1)
        
        # Compute histograms
        ref_hist, _ = np.histogram(reference, bins=bins)
        cur_hist, _ = np.histogram(current, bins=bins)
        
        # Avoid zero counts
        ref_hist = ref_hist + 1
        cur_hist = cur_hist + 1
        
        # Normalize
        ref_hist = ref_hist / ref_hist.sum()
        cur_hist = cur_hist / cur_hist.sum()
        
        # Chi-square test
        statistic, p_value = stats.chisquare(cur_hist, ref_hist)
        
        return float(statistic), float(p_value)
    
    def population_stability_index(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        n_bins: int = 10
    ) -> float:
        """
        Compute Population Stability Index (PSI).
        
        PSI < 0.1: No significant change
        0.1 <= PSI < 0.2: Moderate change
        PSI >= 0.2: Significant change
        
        Args:
            reference: Reference distribution
            current: Current distribution
            n_bins: Number of bins
        
        Returns:
            PSI value
        """
        if len(reference) == 0 or len(current) == 0:
            return 0.0
        
        # Create bins
        all_values = np.concatenate([reference, current])
        bins = np.linspace(np.min(all_values), np.max(all_values), n_bins + 1)
        
        # Compute histograms
        ref_hist, _ = np.histogram(reference, bins=bins)
        cur_hist, _ = np.histogram(current, bins=bins)
        
        # Avoid zero counts
        ref_hist = ref_hist + 1
        cur_hist = cur_hist + 1
        
        # Normalize to proportions
        ref_prop = ref_hist / ref_hist.sum()
        cur_prop = cur_hist / cur_hist.sum()
        
        # Compute PSI
        psi = np.sum((cur_prop - ref_prop) * np.log(cur_prop / ref_prop))
        
        return float(psi)
    
    def jensen_shannon_divergence(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        n_bins: int = 10
    ) -> float:
        """
        Compute Jensen-Shannon divergence.
        
        Args:
            reference: Reference distribution
            current: Current distribution
            n_bins: Number of bins
        
        Returns:
            JS divergence value
        """
        if len(reference) == 0 or len(current) == 0:
            return 0.0
        
        # Create bins
        all_values = np.concatenate([reference, current])
        bins = np.linspace(np.min(all_values), np.max(all_values), n_bins + 1)
        
        # Compute histograms
        ref_hist, _ = np.histogram(reference, bins=bins)
        cur_hist, _ = np.histogram(current, bins=bins)
        
        # Avoid zero counts
        ref_hist = ref_hist + 1
        cur_hist = cur_hist + 1
        
        # Normalize
        ref_prop = ref_hist / ref_hist.sum()
        cur_prop = cur_hist / cur_hist.sum()
        
        # Average distribution
        avg_prop = (ref_prop + cur_prop) / 2
        
        # JS divergence
        js = 0.5 * stats.entropy(ref_prop, avg_prop) + 0.5 * stats.entropy(cur_prop, avg_prop)
        
        return float(js)


class DistanceDriftDetector:
    """
    Distance-based drift detection.
    
    Uses distance metrics to measure distribution changes:
    - Wasserstein distance
    - Maximum Mean Discrepancy (MMD)
    - Energy distance
    """
    
    def __init__(self, threshold: float = 0.1):
        """
        Initialize distance detector.
        
        Args:
            threshold: Distance threshold for drift detection
        """
        self.threshold = threshold
    
    def wasserstein_distance(
        self,
        reference: np.ndarray,
        current: np.ndarray
    ) -> float:
        """
        Compute Wasserstein (Earth Mover's) distance.
        
        Args:
            reference: Reference distribution
            current: Current distribution
        
        Returns:
            Wasserstein distance
        """
        if len(reference) == 0 or len(current) == 0:
            return 0.0
        
        return float(stats.wasserstein_distance(reference, current))
    
    def maximum_mean_discrepancy(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        kernel: str = 'rbf'
    ) -> float:
        """
        Compute Maximum Mean Discrepancy (MMD).
        
        Args:
            reference: Reference samples
            current: Current samples
            kernel: Kernel type ('rbf', 'linear')
        
        Returns:
            MMD value
        """
        if len(reference) == 0 or len(current) == 0:
            return 0.0
        
        # Reshape if needed
        if reference.ndim == 1:
            reference = reference.reshape(-1, 1)
        if current.ndim == 1:
            current = current.reshape(-1, 1)
        
        # Compute kernel matrices
        if kernel == 'rbf':
            gamma = 1.0 / reference.shape[1]
            K_rr = np.exp(-gamma * cdist(reference, reference, 'sqeuclidean'))
            K_cc = np.exp(-gamma * cdist(current, current, 'sqeuclidean'))
            K_rc = np.exp(-gamma * cdist(reference, current, 'sqeuclidean'))
        else:
            K_rr = reference @ reference.T
            K_cc = current @ current.T
            K_rc = reference @ current.T
        
        # MMD statistic
        mmd = np.mean(K_rr) + np.mean(K_cc) - 2 * np.mean(K_rc)
        
        return float(max(0, mmd))
    
    def energy_distance(
        self,
        reference: np.ndarray,
        current: np.ndarray
    ) -> float:
        """
        Compute energy distance.
        
        Args:
            reference: Reference distribution
            current: Current distribution
        
        Returns:
            Energy distance
        """
        if len(reference) == 0 or len(current) == 0:
            return 0.0
        
        # Reshape if needed
        if reference.ndim == 1:
            reference = reference.reshape(-1, 1)
        if current.ndim == 1:
            current = current.reshape(-1, 1)
        
        # Compute distances
        d_rc = np.mean(cdist(reference, current, 'euclidean'))
        d_rr = np.mean(cdist(reference, reference, 'euclidean'))
        d_cc = np.mean(cdist(current, current, 'euclidean'))
        
        energy = 2 * d_rc - d_rr - d_cc
        
        return float(max(0, energy))


class SequentialDriftDetector:
    """
    Sequential drift detection for streaming data.
    
    Implements online drift detection methods:
    - ADWIN (Adaptive Windowing)
    - Page-Hinkley test
    - DDM (Drift Detection Method)
    """
    
    def __init__(self, method: str = 'adwin', delta: float = 0.002):
        """
        Initialize sequential detector.
        
        Args:
            method: Detection method
            delta: Sensitivity parameter
        """
        self.method = method
        self.delta = delta
        self.window = deque()
        self.sum = 0.0
        self.sum_sq = 0.0
        self.n = 0
        
        # Page-Hinkley parameters
        self.ph_sum = 0.0
        self.ph_min = float('inf')
        self.ph_threshold = 50.0
        self.ph_delta = 0.005
        
        # DDM parameters
        self.ddm_n = 0
        self.ddm_p = 0.0
        self.ddm_s = 0.0
        self.ddm_p_min = float('inf')
        self.ddm_s_min = float('inf')
        self.ddm_warning_level = 2.0
        self.ddm_drift_level = 3.0
    
    def add_element(self, value: float) -> Optional[DriftDetectionResult]:
        """
        Add element and check for drift.
        
        Args:
            value: New observation
        
        Returns:
            DriftDetectionResult if drift detected, None otherwise
        """
        self.window.append(value)
        self.sum += value
        self.sum_sq += value ** 2
        self.n += 1
        
        if self.method == 'adwin':
            return self._check_adwin()
        elif self.method == 'page_hinkley':
            return self._check_page_hinkley(value)
        elif self.method == 'ddm':
            return self._check_ddm(value)
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def _check_adwin(self) -> Optional[DriftDetectionResult]:
        """Check for drift using ADWIN algorithm."""
        if len(self.window) < 10:
            return None
        
        # Check different window sizes
        n = len(self.window)
        window_list = list(self.window)
        
        for w in range(n // 2, n - 1):
            # Split window
            left = window_list[:w]
            right = window_list[w:]
            
            if len(left) < 5 or len(right) < 5:
                continue
            
            # Compute means
            mean_left = np.mean(left)
            mean_right = np.mean(right)
            
            # Compute threshold
            m = 1.0 / len(left) + 1.0 / len(right)
            threshold = np.sqrt(2 * m * np.log(2 / self.delta))
            
            if abs(mean_left - mean_right) >= threshold:
                # Drift detected
                self.window = deque(right)
                self.sum = sum(right)
                self.sum_sq = sum(x ** 2 for x in right)
                self.n = len(right)
                
                return DriftDetectionResult(
                    drift_detected=True,
                    drift_type=DriftType.DATA_DRIFT,
                    severity=DriftSeverity.MEDIUM,
                    score=float(abs(mean_left - mean_right) / threshold),
                    p_value=self.delta,
                    statistic=float(abs(mean_left - mean_right)),
                    details={
                        'method': 'adwin',
                        'window_split': w,
                        'mean_left': float(mean_left),
                        'mean_right': float(mean_right),
                        'threshold': float(threshold)
                    },
                    timestamp=float(len(self.window)),
                    window_size=len(self.window)
                )
        
        return None
    
    def _check_page_hinkley(self, value: float) -> Optional[DriftDetectionResult]:
        """Check for drift using Page-Hinkley test."""
        self.ph_sum += value - self.ph_delta
        self.ph_min = min(self.ph_min, self.ph_sum)
        
        if self.ph_sum - self.ph_min > self.ph_threshold:
            # Drift detected
            self.ph_sum = 0.0
            self.ph_min = float('inf')
            
            return DriftDetectionResult(
                drift_detected=True,
                drift_type=DriftType.DATA_DRIFT,
                severity=DriftSeverity.MEDIUM,
                score=float((self.ph_sum - self.ph_min) / self.ph_threshold),
                p_value=None,
                statistic=float(self.ph_sum - self.ph_min),
                details={
                    'method': 'page_hinkley',
                    'threshold': self.ph_threshold
                },
                timestamp=float(self.n),
                window_size=self.n
            )
        
        return None
    
    def _check_ddm(self, value: float) -> Optional[DriftDetectionResult]:
        """Check for drift using DDM method."""
        self.ddm_n += 1
        self.ddm_p += (value - self.ddm_p) / self.ddm_n
        self.ddm_s = np.sqrt(self.ddm_p * (1 - self.ddm_p) / self.ddm_n)
        
        if self.ddm_n < 30:
            return None
        
        if self.ddm_p + self.ddm_s < self.ddm_p_min + self.ddm_s_min:
            self.ddm_p_min = self.ddm_p
            self.ddm_s_min = self.ddm_s
        
        if self.ddm_p + self.ddm_s > self.ddm_p_min + self.ddm_drift_level * self.ddm_s_min:
            # Drift detected
            return DriftDetectionResult(
                drift_detected=True,
                drift_type=DriftType.DATA_DRIFT,
                severity=DriftSeverity.HIGH,
                score=float((self.ddm_p + self.ddm_s) / (self.ddm_p_min + self.ddm_drift_level * self.ddm_s_min)),
                p_value=None,
                statistic=float(self.ddm_p + self.ddm_s),
                details={
                    'method': 'ddm',
                    'p': float(self.ddm_p),
                    's': float(self.ddm_s),
                    'p_min': float(self.ddm_p_min),
                    's_min': float(self.ddm_s_min)
                },
                timestamp=float(self.ddm_n),
                window_size=self.ddm_n
            )
        
        return None


class DriftDetectionEngine:
    """
    Main drift detection engine.
    
    Coordinates multiple drift detection methods and provides
    a unified interface for drift monitoring.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize drift detection engine.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Initialize detectors
        self.statistical_detector = StatisticalDriftDetector(
            significance_level=self.config.get('significance_level', 0.05)
        )
        self.distance_detector = DistanceDriftDetector(
            threshold=self.config.get('distance_threshold', 0.1)
        )
        self.sequential_detector = SequentialDriftDetector(
            method=self.config.get('sequential_method', 'adwin'),
            delta=self.config.get('sequential_delta', 0.002)
        )
        
        # Alert history
        self.alerts: List[DriftAlert] = []
        self.alert_counter = 0
    
    def detect_drift(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, DriftDetectionResult]:
        """
        Detect drift between reference and current distributions.
        
        Args:
            reference: Reference data
            current: Current data
            feature_names: Names of features (optional)
        
        Returns:
            Dictionary of drift detection results per method
        """
        results = {}
        
        # Statistical tests
        ks_stat, ks_p = self.statistical_detector.ks_test(reference, current)
        results['ks_test'] = DriftDetectionResult(
            drift_detected=ks_p < self.statistical_detector.significance_level,
            drift_type=DriftType.DATA_DRIFT,
            severity=self._compute_severity(ks_p),
            score=ks_stat,
            p_value=ks_p,
            statistic=ks_stat,
            details={'test': 'kolmogorov_smirnov'},
            timestamp=0.0,
            window_size=len(current)
        )
        
        # Distance metrics
        w_dist = self.distance_detector.wasserstein_distance(reference, current)
        results['wasserstein'] = DriftDetectionResult(
            drift_detected=w_dist > self.distance_detector.threshold,
            drift_type=DriftType.DATA_DRIFT,
            severity=self._compute_severity_from_distance(w_dist),
            score=min(w_dist / self.distance_detector.threshold, 1.0),
            p_value=None,
            statistic=w_dist,
            details={'distance': 'wasserstein'},
            timestamp=0.0,
            window_size=len(current)
        )
        
        # PSI
        psi = self.statistical_detector.population_stability_index(reference, current)
        results['psi'] = DriftDetectionResult(
            drift_detected=psi > 0.2,
            drift_type=DriftType.DATA_DRIFT,
            severity=self._compute_severity_from_psi(psi),
            score=min(psi / 0.2, 1.0),
            p_value=None,
            statistic=psi,
            details={'metric': 'population_stability_index'},
            timestamp=0.0,
            window_size=len(current)
        )
        
        # Generate alerts for significant drift
        for method, result in results.items():
            if result.drift_detected and result.severity in [DriftSeverity.HIGH, DriftSeverity.CRITICAL]:
                self._generate_alert(result, method)
        
        return results
    
    def _compute_severity(self, p_value: float) -> DriftSeverity:
        """Compute severity from p-value."""
        if p_value > 0.1:
            return DriftSeverity.NONE
        elif p_value > 0.05:
            return DriftSeverity.LOW
        elif p_value > 0.01:
            return DriftSeverity.MEDIUM
        elif p_value > 0.001:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL
    
    def _compute_severity_from_distance(self, distance: float) -> DriftSeverity:
        """Compute severity from distance metric."""
        if distance < 0.05:
            return DriftSeverity.NONE
        elif distance < 0.1:
            return DriftSeverity.LOW
        elif distance < 0.2:
            return DriftSeverity.MEDIUM
        elif distance < 0.5:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL
    
    def _compute_severity_from_psi(self, psi: float) -> DriftSeverity:
        """Compute severity from PSI value."""
        if psi < 0.1:
            return DriftSeverity.NONE
        elif psi < 0.2:
            return DriftSeverity.LOW
        elif psi < 0.3:
            return DriftSeverity.MEDIUM
        elif psi < 0.5:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL
    
    def _generate_alert(self, result: DriftDetectionResult, method: str):
        """Generate drift alert."""
        self.alert_counter += 1
        alert = DriftAlert(
            alert_id=f"drift_{self.alert_counter}",
            drift_type=result.drift_type,
            severity=result.severity,
            message=f"Drift detected using {method}: score={result.score:.3f}",
            details=result.details,
            timestamp=result.timestamp
        )
        self.alerts.append(alert)
        logger.warning(f"Drift alert: {alert.message}")
    
    def get_alerts(
        self,
        severity: Optional[DriftSeverity] = None,
        acknowledged: Optional[bool] = None
    ) -> List[DriftAlert]:
        """Get filtered alerts."""
        filtered = self.alerts
        
        if severity:
            filtered = [a for a in filtered if a.severity == severity]
        
        if acknowledged is not None:
            filtered = [a for a in filtered if a.acknowledged == acknowledged]
        
        return filtered
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False
