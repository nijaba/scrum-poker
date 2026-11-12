"""Results on reveal: RR-01 to RR-05."""

from app.room.results import compute_results
from app.room.scales import fibonacci, tshirt


def votes(scale, *labels):
    return [scale.card(label) for label in labels]


def test_rr01_split_vote_shows_most_chosen():
    scale = fibonacci()
    results = compute_results(votes(scale, "3", "5", "5"), scale.cards)

    assert results.average == 4.3
    assert results.median == 5
    assert results.consensus is False
    assert (results.top_label, results.top_count, results.votes) == ("5", 2, 3)


def test_rr02_unanimous_vote_is_consensus():
    scale = fibonacci()
    results = compute_results(votes(scale, "5", "5", "5"), scale.cards)

    assert results.average == 5.0
    assert results.median == 5
    assert results.consensus is True
    assert results.top_label == "5"


def test_rr03_question_mark_is_left_out():
    scale = fibonacci()
    results = compute_results(votes(scale, "3", "5", "?"), scale.cards)

    assert results.average == 4.0
    assert results.median == 4
    assert results.consensus is False


def test_rr04_tshirt_counts_by_mapped_value():
    scale = tshirt({"S": 2, "M": 3, "L": 5})
    results = compute_results(votes(scale, "S", "M", "M"), scale.cards)

    assert results.average == 2.7
    assert results.median == 3
    assert (results.top_label, results.top_count) == ("M", 2)


def test_rr05_all_question_marks_show_no_average_or_median():
    scale = fibonacci()
    results = compute_results(votes(scale, "?", "?", "?"), scale.cards)

    assert results.average is None
    assert results.median is None
    assert results.to_dict()["average"] is None


def test_average_rounds_half_up():
    scale = fibonacci()
    # 1, 2, 2, 2 -> 1.75 -> 1.8
    assert compute_results(votes(scale, "1", "2", "2", "2"), scale.cards).average == 1.8


def test_no_votes_reveals_empty_results():
    results = compute_results([], fibonacci().cards)

    assert results.votes == 0
    assert results.consensus is False
    assert results.top_label is None
