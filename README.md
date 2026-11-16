
# MP3 Movie API

This project is a FastAPI application for uploading, storing, processing, and retrieving movie data. Users can upload a CSV file containing movie titles, release years, ratings, and genres. The application uses SQLite to store movie records persistently, allowing data to remain available after restarting the server. The `database.py` module manages database connections and table initialization, while `storage.py` handles SQL operations such as inserting, retrieving, counting, filtering, and sorting movies. The `data_pipeline` modules validate and clean movie data by removing duplicates, handling missing values, and filtering outliers. The `cache.py` module uses FakeRedis to cache movie retrieval responses for 90 seconds, reducing repeated database queries. Cached responses are automatically invalidated after a successful upload or processing operation.

## Running the API

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the server:

```bash
python -m uvicorn main:app --reload
```

Open the API documentation at:

http://127.0.0.1:8000/docs

## Running Tests

```bash
python -m pytest tests -v
```

## Example Processing Request

Endpoint: `POST /movies/process`

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {
      "enabled": true,
      "axis": "rows"
    },
    "outliers": {
      "enabled": true,
      "columns": ["rating"],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}
```

Expected response for the provided `sample_movies.csv`:

```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
```
