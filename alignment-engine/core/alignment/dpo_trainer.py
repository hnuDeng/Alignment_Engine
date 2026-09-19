import time
import logging
from typing import Tuple, Dict, Any, Optional, Callable, TypeVar, cast
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.cuda.amp import autocast, GradScaler

logger = logging.getLogger(__name__)

T = TypeVar('T')

class DPOTrainingException(Exception):
    """Base exception for DPO Training errors."""
    pass

class VRAMExhaustionException(DPOTrainingException):
    """Raised when VRAM exceeds safe limits for RTX 5060."""
    pass

class GradientExplosionException(DPOTrainingException):
    """Raised when loss becomes NaN or gradients explode."""
    pass

class ModelLoadException(DPOTrainingException):
    """Raised when model loading fails."""
    pass

def exponential_backoff(max_retries: int = 3, base_delay: float = 1.0) -> Callable:
    """Decorator for exponential backoff retries on arbitrary functions."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = base_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries. Error: {str(e)}")
                        raise e
                    logger.warning(f"Function {func.__name__} failed: {str(e)}. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
            raise RuntimeError("Unreachable")
        return wrapper
    return decorator

class DPOTrainer:
    """
    Direct Preference Optimization (DPO) Trainer.
    Implements from-scratch DPO loss calculation, AMP, and strict VRAM management.
    """
    def __init__(self, model: nn.Module, ref_model: nn.Module, beta: float = 0.1, learning_rate: float = 1e-5):
        self.model = model
        self.ref_model = ref_model
        self.beta = beta
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate)
        self.scaler = GradScaler()
        self.grad_accum_steps = 16
        self.current_step = 0

    @exponential_backoff(max_retries=3, base_delay=2.0)
    def load_weights(self, path: str) -> None:
        """Simulate loading model weights over a network with retries."""
        logger.info(f"Loading weights from {path}...")
        # Simulating potential failure
        if not path:
            raise ModelLoadException("Invalid path for weights.")

    def compute_logps(self, logits: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """
        Compute the log probabilities of the given labels.
        """
        batch_size, seq_len, vocab_size = logits.shape
        assert logits.shape == (batch_size, seq_len, vocab_size), "Invalid logits shape"
        assert labels.shape == (batch_size, seq_len), "Invalid labels shape"

        labels_input = labels.unsqueeze(2)
        # Handle ignore_index (-100)
        mask = (labels_input != -100)
        labels_input = torch.where(mask, labels_input, torch.zeros_like(labels_input))
        
        per_token_logps = torch.gather(logits.log_softmax(-1), dim=2, index=labels_input).squeeze(2)
        return (per_token_logps * mask.squeeze(2)).sum(-1)

    def dpo_loss(
        self,
        policy_chosen_logps: torch.Tensor,
        policy_rejected_logps: torch.Tensor,
        reference_chosen_logps: torch.Tensor,
        reference_rejected_logps: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Compute DPO loss: L = -log(sigmoid(beta * (policy_diff - ref_diff)))
        """
        policy_diff = policy_chosen_logps - policy_rejected_logps
        ref_diff = reference_chosen_logps - reference_rejected_logps
        
        logits = self.beta * (policy_diff - ref_diff)
        loss = -F.logsigmoid(logits).mean()
        
        chosen_rewards = self.beta * (policy_chosen_logps - reference_chosen_logps).detach()
        rejected_rewards = self.beta * (policy_rejected_logps - reference_rejected_logps).detach()
        
        return loss, chosen_rewards, rejected_rewards

    def train_step(
        self,
        chosen_input_ids: torch.Tensor,
        chosen_attention_mask: torch.Tensor,
        chosen_labels: torch.Tensor,
        rejected_input_ids: torch.Tensor,
        rejected_attention_mask: torch.Tensor,
        rejected_labels: torch.Tensor,
    ) -> float:
        """
        Executes a single training step with extreme VRAM tracking and cleanup.
        """
        start_time = time.time()
        logger.info("Starting DPO train step")
        loss_val = 0.0

        try:
            with autocast():
                # Policy model forward
                policy_chosen_logits = self.model(chosen_input_ids, attention_mask=chosen_attention_mask)
                policy_rejected_logits = self.model(rejected_input_ids, attention_mask=rejected_attention_mask)
                
                # Reference model forward (no grad)
                with torch.inference_mode():
                    ref_chosen_logits = self.ref_model(chosen_input_ids, attention_mask=chosen_attention_mask)
                    ref_rejected_logits = self.ref_model(rejected_input_ids, attention_mask=rejected_attention_mask)

                # Compute logprobs
                policy_chosen_logps = self.compute_logps(policy_chosen_logits, chosen_labels)
                policy_rejected_logps = self.compute_logps(policy_rejected_logits, rejected_labels)
                ref_chosen_logps = self.compute_logps(ref_chosen_logits, chosen_labels)
                ref_rejected_logps = self.compute_logps(ref_rejected_logits, rejected_labels)

                loss, _, _ = self.dpo_loss(
                    policy_chosen_logps, policy_rejected_logps,
                    ref_chosen_logps, ref_rejected_logps
                )
                
                loss = loss / self.grad_accum_steps

            if torch.isnan(loss):
                raise GradientExplosionException("NaN loss detected during DPO step")

            self.scaler.scale(loss).backward()
            loss_val = loss.item()

            self.current_step += 1
            if self.current_step % self.grad_accum_steps == 0:
                self.scaler.step(self.optimizer)
                self.scaler.update()
                self.optimizer.zero_grad()

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                raise VRAMExhaustionException("RTX 5060 VRAM Limit Exceeded (8GB max).")
            raise e
        finally:
            # Extreme Defensive Programming: Force GC and VRAM cleanup
            del policy_chosen_logits
            del policy_rejected_logits
            del ref_chosen_logits
            del ref_rejected_logits
            del policy_chosen_logps
            del policy_rejected_logps
            del ref_chosen_logps
            del ref_rejected_logps
            torch.cuda.empty_cache()
            
            elapsed = time.time() - start_time
            logger.info(f"Finished DPO train step. Time: {elapsed:.3f}s. Loss: {loss_val:.4f}")

        return loss_val
