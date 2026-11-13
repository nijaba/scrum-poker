"""Scales: cards with a label and an optional numeric value."""

import pytest

from app.room.errors import CommandError
from app.room.scales import Scale, custom, fibonacci, tshirt


def labels(scale):
    return [c.label for c in scale.cards]


def test_fibonacci_cards():
    scale = fibonacci()

    assert labels(scale) == ["1", "2", "3", "5", "8", "13", "21", "34", "55", "?"]
    assert scale.card("13").value == 13
    assert scale.card("55").value == 55
    assert scale.card("?").value is None


def test_tshirt_default_mapping_is_editable():
    assert tshirt().card("M").value == 3
    assert tshirt({"S": 1, "M": 4}).card("M").value == 4
    assert labels(tshirt({"S": 1, "M": 4})) == ["S", "M", "?"]


def test_custom_list_keeps_order_and_parses_numbers():
    scale = custom(["1", "2", "4", "?", "coffee", {"label": "big", "value": 20}])

    assert labels(scale) == ["1", "2", "4", "?", "coffee", "big"]
    assert scale.card("4").value == 4
    assert scale.card("coffee").value is None
    assert scale.card("big").value == 20


@pytest.mark.parametrize(
    "data",
    [
        {"kind": "custom", "cards": []},
        {"kind": "custom", "cards": ["1", "1"]},
        {"kind": "custom", "cards": [""]},
        {"kind": "custom", "cards": [{"label": "x", "value": -1}]},
        {"kind": "custom", "cards": [{"label": "x", "value": "3"}]},
        {"kind": "tshirt", "mapping": ["S"]},
        {"kind": "roman"},
        "fibonacci",
    ],
)
def test_invalid_scales_are_rejected(data):
    with pytest.raises(CommandError):
        Scale.from_dict(data)


def test_scale_from_dict_round_trips_kind():
    assert Scale.from_dict({"kind": "fibonacci"}) == fibonacci()
    assert Scale.from_dict({"kind": "tshirt", "mapping": {"S": 2}}).kind == "tshirt"
