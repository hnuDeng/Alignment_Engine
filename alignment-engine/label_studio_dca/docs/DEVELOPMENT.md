# Development Guide

## Architecture

### Backend

The backend is organized into three main modules:

1. **Active Learning** (`backend/active_learning/`)
   - `models.py` - Data models
   - `strategies/` - Sampling strategies
   - `selectors/` - Task selectors
   - `api.py` - API interfaces

2. **Data Quality** (`backend/data_quality/`)
   - `models.py` - Data models
   - `assessors/` - Quality assessors
   - `api.py` - API interfaces

3. **Drift Detection** (`backend/drift_detection/`)
   - `models.py` - Data models
   - `detectors/` - Drift detectors
   - `api.py` - API interfaces

### Frontend

The frontend is organized as:

1. **Types** (`frontend/types/`) - TypeScript type definitions
2. **API** (`frontend/api/`) - API service layer
3. **Hooks** (`frontend/hooks/`) - Custom React hooks
4. **Components** (`frontend/components/`) - Reusable UI components
5. **Pages** (`frontend/pages/`) - Page components

## Adding New Features

### Adding a New Strategy

1. Create a new file in `backend/active_learning/strategies/`
2. Implement the `BaseStrategy` interface
3. Register the strategy in `strategies/__init__.py`
4. Add tests in `tests/test_active_learning.py`

### Adding a New Assessor

1. Create a new file in `backend/data_quality/assessors/`
2. Implement the `BaseAssessor` interface
3. Register the assessor in `assessors/engine.py`
4. Add tests in `tests/test_data_quality.py`

### Adding a New Detector

1. Create a new file in `backend/drift_detection/detectors/`
2. Implement the `BaseDriftDetector` interface
3. Add tests in `tests/test_drift_detection.py`

## Code Style

### Python
- Follow PEP 8
- Use type hints
- Write docstrings for all public methods

### TypeScript
- Use TypeScript strict mode
- Define interfaces for all data structures
- Use functional components with hooks

## Testing

Run all tests:
```bash
cd tests
python run_tests.py
```

Run specific module tests:
```bash
python -m pytest test_active_learning.py -v
python -m pytest test_data_quality.py -v
python -m pytest test_drift_detection.py -v
```
