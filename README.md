# ds3-example-project

Scaffolded data science project structure.

## Structure

- `notebooks/` - exploratory notebooks
- `src/` - python package source
- `data/` - raw and processed datasets
- `models/` - saved models
- `results/` - experiment outputs and figures
- `tests/` - unit and integration tests

## Quick start

Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

PlantDex API Base URL:
https://lyot4yhfu8.execute-api.us-west-2.amazonaws.com

Similarity endpoint:
GET /similar?query=tomato&max_results=3&image_only=true