import ray
import time
import logging
from typing import Dict, Any, List
import functools

logger = logging.getLogger(__name__)

class DispatcherException(Exception):
    """Base exception for Ray Dispatcher."""
    pass

class ActorInitializationException(DispatcherException):
    """Raised when Ray actors fail to initialize."""
    pass

class TaskTimeoutException(DispatcherException):
    """Raised when a distributed task times out."""
    pass

class LoadBalanceException(DispatcherException):
    """Raised when load balancing queues are overloaded."""
    pass

def exponential_backoff_ray(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        logger.error(f"Ray task {func.__name__} failed completely: {str(e)}")
                        raise TaskTimeoutException(f"Task failed after {max_retries} retries: {e}")
                    logger.warning(f"Ray task {func.__name__} failed, retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator

@ray.remote(num_gpus=0.1) # Assuming fractional GPU allocation for many decoders
class MediaDecoderActor:
    def __init__(self, actor_id: int):
        self.actor_id = actor_id
        logger.info(f"Initialized MediaDecoderActor {self.actor_id}")
        # In real code, we would initialize the GPU decoder instance here

    @exponential_backoff_ray(max_retries=3)
    def decode_batch(self, batch: List[bytes]) -> List[Any]:
        """
        Simulate decoding a batch of images.
        """
        start_time = time.time()
        # Simulate processing time
        time.sleep(0.01 * len(batch))
        logger.info(f"Actor {self.actor_id} decoded batch of {len(batch)} items in {time.time()-start_time:.3f}s")
        return [{"status": "success", "size": len(b)} for b in batch]

class RayDispatcher:
    def __init__(self, num_actors: int = 4):
        try:
            if not ray.is_initialized():
                ray.init(ignore_reinit_error=True)
            self.actors = [MediaDecoderActor.remote(i) for i in range(num_actors)]
            self.round_robin_idx = 0
        except Exception as e:
            raise ActorInitializationException(f"Failed to init Ray: {e}")

    def dispatch(self, batches: List[List[bytes]]) -> List[Any]:
        """
        Load balance batches across actors using round-robin.
        """
        if not batches:
            return []

        futures = []
        for batch in batches:
            actor = self.actors[self.round_robin_idx]
            futures.append(actor.decode_batch.remote(batch))
            self.round_robin_idx = (self.round_robin_idx + 1) % len(self.actors)

        try:
            results = ray.get(futures, timeout=30.0)
            return results
        except ray.exceptions.GetTimeoutError:
            raise TaskTimeoutException("Ray get() timed out after 30 seconds.")
        except Exception as e:
            raise LoadBalanceException(f"Failed to gather results: {e}")
