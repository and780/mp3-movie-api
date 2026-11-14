
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
    assert report["cleaning_report"]["rows_after"] == 18

    response = client.get("/movies")

    assert response.status_code == 200

    data = response.json()
    assert data["total_rows"] == 18


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
