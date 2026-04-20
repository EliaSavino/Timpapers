from timpapers.services.normalization import normalize_openalex_work


def test_normalize_openalex_work_extracts_expected_fields() -> None:
    raw = {
        "id": "https://openalex.org/W123",
        "display_name": "A Paper",
        "publication_year": 2024,
        "doi": "https://doi.org/10.1000/test",
        "cited_by_count": 42,
        "primary_location": {"source": {"display_name": "Nature"}},
        "authorships": [
            {"author": {"display_name": "Alice"}},
            {"author": {"display_name": "Bob"}},
        ],
    }
    normalized = normalize_openalex_work(raw)
    assert normalized["title"] == "A Paper"
    assert normalized["doi"] == "10.1000/test"
    assert normalized["citation_count"] == 42
    assert normalized["author_list"] == "Alice, Bob"
