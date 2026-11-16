
import main
from src import MovieStorage

def test_upload_csv(client, sample_csv_bytes):
    response = client.post(
        "/upload",
        files={
            "file": ("sample_movies.csv", sample_csv_bytes, "text/csv")
        }
    )

    assert response.status_code == 200

    data = response.json()
    assert data["filename"] == "sample_movies.csv"
    assert data["rows"] == 20
    assert data["columns"] == 4
    assert data["column_names"] == [
        "title", "release_year", "rating", "genre"
    ]


def test_get_movies(client, uploaded_movies):
    response = client.get("/movies", params={"limit": 2})

    assert response.status_code == 200

    data = response.json()
    assert data["total_rows"] == 20
    assert len(data["data"]) == 2

    assert data["data"][0]["title"] == "Movie A"
    assert data["data"][1]["title"] == "Movie B"


def test_search_movies(client, uploaded_movies):
    response = client.get(
        "/movies/search",
        params={
            "columns": ["title", "rating"],
            "min_rating": 8.5,
            "limit": 2
        }
    )

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2

    assert data[0] == {
        "id": 4,
        "title": "Movie C",
        "rating": 9.0
    }

    assert data[1] == {
        "id": 2,
        "title": "Movie B",
        "rating": 8.5
    }


def test_process_and_retrieve(client, uploaded_movies, processing_body):
    response = client.post(
        "/movies/process",
        json=processing_body
    )

    assert response.status_code == 200

    report = response.json()
    assert report["validation_rows_removed"] == 0
    assert report["cleaning_report"]["rows_before"] == 20
    assert report["cleaning_report"]["rows_after"] == 16

    response = client.get("/movies")

    assert response.status_code == 200

    data = response.json()
    assert data["total_rows"] == 16


def test_empty_movies(client):
    response = client.get("/movies")

    assert response.status_code == 200
    assert response.json() == {
        "data": [],
        "total_rows": 0
    }


def test_invalid_search_column(client, uploaded_movies):
    response = client.get(
        "/movies/search",
        params={"columns": "invalid_column"}
    )

    assert response.status_code == 400


def test_invalid_upload(client):
    response = client.post(
        "/upload",
        files={
            "file": ("invalid.txt", b"Not a CSV", "text/plain")
        }
    )

    assert response.status_code == 400


def test_upload_replaces_movies(client, sample_csv_bytes):
    for _ in range(2):
        response = client.post(
            "/upload",
            files={
                "file": ("sample_movies.csv", sample_csv_bytes, "text/csv")
            }
        )
        assert response.status_code == 200

    response = client.get("/movies")

    assert response.json()["total_rows"] == 20



def test_movies_persist(client, test_storage, uploaded_movies):
    new_storage = MovieStorage(test_storage.db_path)

    df = new_storage.get()

    assert new_storage.count_movies() == 20
    assert len(df) == 20
    assert df.columns.tolist() == [
        "title", "release_year", "rating", "genre"
    ]

    expected_titles = ["Movie " + chr(i) for i in range(65, 83)]
    expected_titles.insert(2, "Movie B")
    expected_titles.insert(5, "Movie D")

    assert df["title"].tolist() == expected_titles

    stored_rows = new_storage.select_columns(["title"], limit=100)
    response = client.get("/movies", params={"limit": 100})

    assert response.status_code == 200
    assert [row["id"] for row in stored_rows] == list(range(1, 21))
    assert [row["id"] for row in response.json()["data"]] == list(range(1, 21))


def test_cache_and_processing(client, uploaded_movies, processing_body):
    response_100 = client.get("/movies", params={"limit": 100})
    response_1 = client.get("/movies", params={"limit": 1})

    assert response_100.status_code == 200
    assert response_1.status_code == 200

    assert main.cache.get(100) == response_100.json()
    assert main.cache.get(1) == response_1.json()

    repeated_response = client.get("/movies", params={"limit": 100})

    assert repeated_response.status_code == 200
    assert repeated_response.json() == response_100.json()

    process_response = client.post(
        "/movies/process",
        json=processing_body
    )

    assert process_response.status_code == 200

    report = process_response.json()
    assert report["validation_rows_removed"] == 0
    assert report["cleaning_report"]["rows_before"] == 20
    assert report["cleaning_report"]["rows_after"] == 16
    assert report["cleaning_report"]["rows_removed"] == 4

    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    response = client.get("/movies", params={"limit": 100})

    assert response.status_code == 200

    data = response.json()
    assert data["total_rows"] == 16
    assert [row["title"] for row in data["data"]] == [
        "Movie " + chr(i) for i in range(65, 81)
    ]
    assert [row["id"] for row in data["data"]] == list(range(1, 17))

    assert main.cache.get(100) == data


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    response = client.get("/movies", params={"limit": 100})

    assert response.status_code == 200
    original_data = response.json()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Database should not be queried on cache HIT")

    monkeypatch.setattr(
        main.storage, "select_columns", fail_if_called
    )
    monkeypatch.setattr(
        main.storage, "count_movies", fail_if_called
    )

    cached_response = client.get("/movies", params={"limit": 100})

    assert cached_response.status_code == 200
    assert cached_response.json() == original_data
