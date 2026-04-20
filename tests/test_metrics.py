from timpapers.services.metrics import PaperMetricInput, compute_h_index, compute_i10_index, hindex_frontier


def test_h_index_calculation() -> None:
    assert compute_h_index([25, 10, 8, 5, 3]) == 4
    assert compute_h_index([1, 1, 1]) == 1
    assert compute_h_index([]) == 0


def test_i10_index_calculation() -> None:
    assert compute_i10_index([10, 9, 50, 11]) == 3


def test_frontier_binning() -> None:
    papers = [
        PaperMetricInput(1, "A", 20),
        PaperMetricInput(2, "B", 10),
        PaperMetricInput(3, "C", 9),
        PaperMetricInput(4, "D", 8),
        PaperMetricInput(5, "E", 2),
    ]
    analysis = hindex_frontier(papers)
    assert analysis["h_index"] == 4
    assert len(analysis["contributors"]) == 4
    assert analysis["near_misses"][0]["paper_id"] == 5
