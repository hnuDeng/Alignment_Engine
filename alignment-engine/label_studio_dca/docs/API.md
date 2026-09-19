# API Reference

## Active Learning API

### create_config

Create active learning configuration.

**Parameters:**
- `project_id` (int): Project ID
- `strategy` (str): Strategy name ('uncertainty', 'diversity', 'committee', 'hybrid', 'random')
- `batch_size` (int): Batch size for selection

**Returns:** `ActiveLearningConfig`

### select_tasks

Select tasks for annotation.

**Parameters:**
- `config_id` (int): Configuration ID
- `tasks` (List[TaskData]): List of tasks
- `predictions` (Dict): Predictions for tasks

**Returns:** `SelectionResult`

---

## Data Quality API

### run_assessment

Run quality assessment.

**Parameters:**
- `project_id` (int): Project ID
- `tasks` (List[Dict]): Task data
- `annotations` (List[Dict]): Annotation data

**Returns:** `QualityReport`

### get_dashboard

Get dashboard data.

**Parameters:**
- `project_id` (int): Project ID

**Returns:** `Dict` with dashboard data

---

## Drift Detection API

### create_baseline

Create drift baseline.

**Parameters:**
- `project_id` (int): Project ID
- `name` (str): Baseline name
- `tasks` (List[Dict]): Task data

**Returns:** `DriftBaseline`

### run_detection

Run drift detection.

**Parameters:**
- `project_id` (int): Project ID
- `baseline_id` (int): Baseline ID
- `current_tasks` (List[Dict]): Current task data

**Returns:** `DriftReport`
