"""Tests for core template tags and filters."""

import pytest

from core.templatetags.crumbs_extras import in_wishlist


@pytest.mark.parametrize(
    ("wishlist_product_ids", "product_id", "expected"),
    [
        ([1, 2, 3], 2, True),
        ([1, 2, 3], 9, False),
        (["1", "2", "3"], 2, True),
        ("1,2,3", 2, True),
        ("1, 2 , 3", 3, True),
        (None, 1, False),
        ("", 1, False),
        ("   ", 1, False),
        ("abc,def", 1, False),
        ({1, 2, 3}, 2, True),
        (frozenset({1, 2, 3}), 1, True),
        ((1, 2), 2, True),
        (42, 42, True),
        ([1, "bad", 3], 3, True),
        ([1, None, 3], 2, False),
        ([], 1, False),
        ("1,2,bad,4", 4, True),
        (None, None, False),
        ("1,2,3", "2", True),
        ("1,2,3", "bad", False),
    ],
)
def test_in_wishlist_normalizes_inputs(wishlist_product_ids, product_id, expected):
    assert in_wishlist(wishlist_product_ids, product_id) is expected


def test_in_wishlist_accepts_values_list_like_iterable():
    class FakeValuesList:
        def __iter__(self):
            yield 10
            yield "11"

    assert in_wishlist(FakeValuesList(), 11) is True
    assert in_wishlist(FakeValuesList(), 99) is False


def test_in_wishlist_never_raises_for_bad_context():
    assert in_wishlist(object(), 1) is False
    assert in_wishlist("1,2,3", object()) is False
