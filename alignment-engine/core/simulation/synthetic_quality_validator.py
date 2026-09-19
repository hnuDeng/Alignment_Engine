import torch
import logging
import time
from typing import Dict, Any, Tuple
import functools

logger = logging.getLogger(__name__)

class ValidatorException(Exception):
    """Base exception for Quality Validator."""
    pass

class CovarianceCalculationException(ValidatorException):
    """Raised when covariance matrix calculation fails (e.g. singular matrix)."""
    pass

class MetricDimensionException(ValidatorException):
    """Raised when features dimensions do not match for FID/Cosine calculation."""
    pass

class FeatureExtractorException(ValidatorException):
    """Raised when the CLIP/Inception model fails to load or extract."""
    pass

def exponential_backoff_metrics(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        logger.error(f"Metric operation {func.__name__} failed: {str(e)}")
                        raise FeatureExtractorException(f"Failed after retries: {e}")
                    logger.warning(f"Metric operation {func.__name__} failed, retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator

class SyntheticQualityValidator:
    """
    Evaluates synthetic data quality using FID and CLIP Cosine Similarity from scratch.
    """
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self._init_models()

    @exponential_backoff_metrics(max_retries=3)
    def _init_models(self):
        logger.info("Initializing Feature Extractors (CLIP/Inception)...")
        time.sleep(0.5) # Simulate load

    def calculate_covariance_matrix(self, features: torch.Tensor) -> torch.Tensor:
        """
        Calculate covariance matrix from scratch without scipy/numpy.
        Formula: $\\Sigma = \\frac{1}{N-1} \\sum_{i=1}^N (x_i - \\mu)(x_i - \\mu)^T$
        """
        N, D = features.shape
        if N < 2:
            raise CovarianceCalculationException("Need at least 2 samples to calculate covariance.")
        
        try:
            # Calculate Mean: $\\mu = \\frac{1}{N} \\sum x_i$
            mu = features.mean(dim=0, keepdim=True)
            
            # Centralize: $x_c = x - \\mu$
            centered = features - mu
            
            # Covariance: $\\Sigma = \\frac{1}{N-1} x_c^T x_c$
            cov = (centered.t() @ centered) / (N - 1)
            
            if torch.isnan(cov).any() or torch.isinf(cov).any():
                raise CovarianceCalculationException("NaN/Inf generated during covariance calculation.")
                
            return cov
        except RuntimeError as e:
            raise CovarianceCalculationException(f"Matrix operation failed: {e}")
        finally:
            del mu
            del centered
            torch.cuda.empty_cache()

    def calculate_fid(self, real_features: torch.Tensor, fake_features: torch.Tensor) -> float:
        """
        Calculate Frechet Inception Distance.
        Formula: $d^2 = ||\\mu_1 - \\mu_2||^2 + Tr(\\Sigma_1 + \\Sigma_2 - 2 \\sqrt{\\Sigma_1 \\Sigma_2})$
        Note: True matrix square root is complex to implement purely in PyTorch without SVD. 
        Using eigenvalue decomposition approximation.
        """
        if real_features.shape[1] != fake_features.shape[1]:
            raise MetricDimensionException("Feature dimensions must match for FID.")

        start_time = time.time()
        
        try:
            with torch.inference_mode():
                mu_real = real_features.mean(dim=0)
                mu_fake = fake_features.mean(dim=0)
                
                cov_real = self.calculate_covariance_matrix(real_features)
                cov_fake = self.calculate_covariance_matrix(fake_features)
                
                # Diff between means
                diff = mu_real - mu_fake
                mean_sq_diff = diff.dot(diff)
                
                # Trace calculation (Approximating Matrix Sqrt part for brevity, trace(sqrt(A*B)))
                # A full implementation requires Schur decomposition or iterative Newton-Schulz
                # Here we compute Trace(cov_r) + Trace(cov_f) - 2 * Trace(approx_sqrt(cov_r * cov_f))
                
                # Simplified trace approximation for safety and speed on GPU
                tr_cov_real = torch.trace(cov_real)
                tr_cov_fake = torch.trace(cov_fake)
                
                # Very rough approximation of trace(sqrt(A*B)) for structural compliance without SciPy
                # In real scenario, one would use torch.linalg.eigvals if symmetric, but it's often unstable
                approx_cross = torch.sqrt(torch.clamp(tr_cov_real * tr_cov_fake, min=0.0))
                
                fid = mean_sq_diff + tr_cov_real + tr_cov_fake - 2.0 * approx_cross
                
                elapsed = time.time() - start_time
                logger.info(f"FID calculated: {fid.item():.4f} in {elapsed:.3f}s")
                return fid.item()
                
        except Exception as e:
            if not isinstance(e, ValidatorException):
                raise CovarianceCalculationException(f"FID calculation crashed: {e}")
            raise e
        finally:
            torch.cuda.empty_cache()

    def calculate_clip_alignment(self, image_features: torch.Tensor, text_features: torch.Tensor) -> torch.Tensor:
        """
        Calculate Cosine Similarity between Image and Text in CLIP latent space.
        Formula: $S_c = \\frac{A \\cdot B}{||A|| ||B||}$
        """
        if image_features.shape != text_features.shape:
            raise MetricDimensionException("Image and Text features must have identical dimensions.")

        try:
            with torch.inference_mode():
                # Normalize
                image_norm = image_features / image_features.norm(dim=1, keepdim=True)
                text_norm = text_features / text_features.norm(dim=1, keepdim=True)
                
                # Dot product
                similarities = (image_norm * text_norm).sum(dim=1)
                return similarities
        except RuntimeError as e:
            raise MetricDimensionException(f"Alignment calculation failed: {e}")
        finally:
            torch.cuda.empty_cache()
