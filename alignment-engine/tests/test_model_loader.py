import pytest
from unittest.mock import MagicMock, patch

from core.inference.model_loader import (
    ModelLoader,
    QuantizationConfig,
    ModelLoadConfig,
    DummyModel
)

class TestModelLoader:
    def test_initialization_mock_mode(self):
        with patch.dict('sys.modules', {'torch': None}):
            loader = ModelLoader()
            assert loader.mock_mode is True
            assert loader.is_loaded is False

    def test_initialization_cuda_available(self):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "Test GPU"
        mock_torch.cuda.get_device_properties.return_value = MagicMock(total_mem=8*10**9)
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            loader = ModelLoader()
            assert loader.mock_mode is False
            assert loader._cuda_available is True
            assert loader._torch_available is True

    def test_load_dummy_model(self):
        loader = ModelLoader()
        loader.mock_mode = True
        model = loader.load()
        assert isinstance(model, DummyModel)
        assert loader.is_loaded is True
        assert loader.model_info.model_name == "DummyModel"
        
        # Test DummyModel generation
        assert model() is None
        assert model.to("cuda") == model
        assert model.eval() == model

    def test_load_fallback_from_bitsandbytes(self):
        loader = ModelLoader()
        loader.mock_mode = False
        
        # Mock load_quantized_4bit to fail with ImportError
        with patch.object(loader, '_load_quantized_4bit', side_effect=ImportError("No bnb")):
            with patch.object(loader, '_load_fp16', return_value="FP16Model") as mock_fp16:
                model = loader.load()
                assert model == "FP16Model"
                mock_fp16.assert_called_once()

    def test_load_fallback_to_dummy(self):
        loader = ModelLoader()
        loader.mock_mode = False
        
        with patch.object(loader, '_load_quantized_4bit', side_effect=Exception("Failed")):
            with patch.object(loader, '_load_fp16', side_effect=Exception("Failed FP16")):
                model = loader.load()
                assert isinstance(model, DummyModel)

    def test_unload_mock(self):
        loader = ModelLoader()
        loader.load()
        assert loader.is_loaded is True
        loader.unload()
        assert loader.is_loaded is False
        assert loader.model_info is None
        assert loader.model is None
        assert loader.processor is None
