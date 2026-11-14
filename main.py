
import io
import json
import logging
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from src import (
    HealthResponse,
    ProcessConfig,
    MovieStorage,
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
    log_requests,
    setup_logging,
)
from src.storage import MOVIE_COLUMNS

from data_pipeline import (
    create_cleaning_report,
    process_data,
    validate_dataframe,
)


setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Movie API", version="1.0.0")
app.middleware("http")(log_requests)

storage = MovieStorage()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Read and store a CSV upload."""
    extension = Path(file.filename or "").suffix.lower()

    if extension != ".csv":
        logger.warning(f"Unsupported file format: {extension}")
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    contents = await file.read()

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as error:
        logger.warning(f"Invalid CSV file: {error}")
        raise HTTPException(status_code=400, detail="Unable to read CSV file") from error

    if len(df.columns) != len(MOVIE_COLUMNS) or set(df.columns) != set(MOVIE_COLUMNS):
        raise HTTPException(status_code=400, detail="Invalid movie columns")

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV file contains no movies")

    df = df[MOVIE_COLUMNS]
    storage.save(df)

    logger.info(f"Uploaded movies: filename={file.filename}, rows={len(df)}")

    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist()
    }


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    """Return stored movies."""
    total_rows = storage.count_movies()
    records = storage.select_columns(MOVIE_COLUMNS, limit)

    logger.info(f"Retrieved movies: returned_rows={len(records)}")

    return {
        "data": records,
        "total_rows": total_rows
    }


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1)
):
    """Search movies by minimum rating."""
    try:
        records = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        logger.warning(f"Movie search failed: {error}")
        raise HTTPException(status_code=400, detail=str(error)) from error

    logger.info(
        f"Queried movies: columns={columns}, "
        f"min_rating={min_rating}, returned_rows={len(records)}"
    )

    return records


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    """Validate and process the stored movie collection."""
    df = storage.get()

    if df.empty:
        logger.warning("No movies available for processing")
        raise HTTPException(status_code=400, detail="No movies available")

    settings = config.model_dump()

    try:
        required_columns = settings["validation"]["required_columns"]
        numeric_columns = settings["validation"]["numeric_columns"]

        for col in numeric_columns:
            if col not in df.columns:
                raise ValueError(f"Missing numeric column: {col}")

        validated_df = validate_dataframe(
            df,
            required_columns,
            numeric_columns
        )

        validation_rows_removed = len(df) - len(validated_df)
        df_before = validated_df.copy()

        processed_df = process_data(validated_df, settings)

        cleaning_report = create_cleaning_report(
            df_before,
            processed_df
        )

    except ValueError as error:
        logger.warning(f"Movie processing failed: {error}")
        raise HTTPException(status_code=400, detail=str(error)) from error

    storage.save(processed_df)

    logger.info(
        f"Processed movies: validation_removed={validation_rows_removed}, "
        f"rows_before={len(df_before)}, rows_after={len(processed_df)}"
    )

    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report
    }
