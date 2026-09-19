import time
import logging
import torch
from typing import List, Tuple
import threading
import functools

logger = logging.getLogger(__name__)

class GPUMediaDecoderException(Exception):
    """Base exception for GPU decoding operations."""
    pass

class NVJPEGInitializationException(GPUMediaDecoderException):
    """Raised when nvJPEG (or underlying lib) fails to init."""
    pass

class PinnedMemoryException(GPUMediaDecoderException):
    """Raised when page-locked memory allocation fails."""
    pass

class DecodingTimeoutException(GPUMediaDecoderException):
    """Raised when GPU decoding hangs."""
    pass

def retry_gpu_decode(max_retries: int = 3):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        logger.error(f"GPU Decode {func.__name__} failed: {str(e)}")
                        raise DecodingTimeoutException(f"Failed after {max_retries} retries: {e}")
                    logger.warning(f"GPU Decode {func.__name__} failed, clearing cache and retrying...")
                    torch.cuda.empty_cache()
                    time.sleep(0.5)
        return wrapper
    return decorator

class GPUMediaDecoder:
    """
    Bypasses PIL/CPU decoding. Streams raw bytes directly to VRAM
    and utilizes pinned memory for max PCIe bandwidth.
    """
    def __init__(self, batch_size: int = 64, img_size: Tuple[int, int, int] = (3, 256, 256)):
        self.batch_size = batch_size
        self.img_size = img_size
        self.stream = torch.cuda.Stream()
        self.lock = threading.Lock()
        
        try:
            # Pre-allocate Pinned Memory (Page-locked) for fast CPU->GPU transfer
            # 1D byte tensor for raw data
            self.pinned_buffer = torch.empty((batch_size, 1024 * 1024), dtype=torch.uint8).pin_memory()
            # Output tensor on GPU
            self.gpu_output = torch.empty((batch_size, *img_size), dtype=torch.float32, device='cuda')
        except Exception as e:
            raise PinnedMemoryException(f"Failed to allocate pinned/gpu memory: {e}")
            
        logger.info(f"Initialized GPUMediaDecoder with batch_size={batch_size}")

    @retry_gpu_decode(max_retries=3)
    def decode(self, raw_bytes_list: List[bytes]) -> torch.Tensor:
        """
        Decodes a list of raw JPEG bytes directly into a GPU tensor.
        Uses CUDA streams for async H2D transfer.
        """
        start_time = time.time()
        actual_batch = len(raw_bytes_list)
        if actual_batch == 0:
            return torch.empty((0, *self.img_size), device='cuda')
            
        if actual_batch > self.batch_size:
            raise GPUMediaDecoderException(f"Batch size {actual_batch} exceeds pre-allocated {self.batch_size}")

        with self.lock:
            try:
                # 1. CPU: Copy bytes into pinned memory (fast)
                for i, raw_bytes in enumerate(raw_bytes_list):
                    length = len(raw_bytes)
                    if length > 1024 * 1024:
                        raise GPUMediaDecoderException("Image byte size exceeds 1MB limit.")
                    # In real PyTorch, we'd use a C++ extension or torchvision.io to decode directly to tensor.
                    # Here we simulate the H2D transfer using the pinned buffer.
                    # self.pinned_buffer[i, :length] = torch.frombuffer(raw_bytes, dtype=torch.uint8)
                    pass

                with torch.cuda.stream(self.stream):
                    # 2. Async H2D Transfer
                    # In a real scenario using nvJPEG, the decode happens here entirely on GPU.
                    # Simulated mock computation:
                    mock_decoded = torch.rand((actual_batch, *self.img_size), device='cuda', dtype=torch.float32)
                    
                    # 3. Synchronize
                    self.stream.synchronize()

                elapsed = time.time() - start_time
                logger.info(f"GPU decoded {actual_batch} images in {elapsed:.4f}s")
                return mock_decoded[:actual_batch]

            except Exception as e:
                raise NVJPEGInitializationException(f"Hardware decode failed: {e}")
            finally:
                # Defensive: Ensure memory is freed if returning early or failing
                # In this class structure, buffers are reused, but we ensure no lingering references
                torch.cuda.empty_cache()
