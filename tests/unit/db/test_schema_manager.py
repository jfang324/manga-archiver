import pytest

from src.manga_archiver.db.schema_manager import _version_compare, _version_key


class TestVersionKey:
    @pytest.mark.parametrize(
        "version, expected",
        [
            ("v1.10.0", (1, 10, 0)),
            ("v1.9.0", (1, 9, 0)),
            ("v1.2.3", (1, 2, 3)),
            ("v2.0.0", (2, 0, 0)),
            ("1.2.3", (1, 2, 3)),
            ("v1.0", (1, 0)),
            ("v1", (1,)),
            ("v1.2.3.4", (1, 2, 3, 4)),
        ],
        ids=[
            "v1_10_0",
            "v1_9_0",
            "v1_2_3",
            "v2_0_0",
            "without_v_prefix",
            "single_minor",
            "single_component",
            "four_components",
        ],
    )
    def test_version_key_parses_correctly(self, version: str, expected: tuple[int, ...]):
        assert _version_key(version) == expected


class TestVersionCompare:
    @pytest.mark.parametrize(
        "a, b, expected",
        [
            ("v1.10.0", "v1.9.0", 1),
            ("v1.9.0", "v1.10.0", -1),
            ("v1.2.0", "v1.2.0", 0),
            ("v1.0", "v1.0", 0),
            ("v1.2.3", "v1.2.3", 0),
            ("v1", "v1.0.0", 0),
            ("v1.0.0", "v1", 0),
            ("v2.0.0", "v1.9.9", 1),
            ("v1.0.0", "v2.0.0", -1),
            ("v1.2.3", "v1.2.4", -1),
            ("v1.2.5", "v1.2.4", 1),
            ("v1.2", "v1.2.0", 0),
            ("v1.2.0", "v1.2", 0),
        ],
        ids=[
            "v1_10_greater_than_v1_9",
            "v1_9_less_than_v1_10",
            "v1_2_0_equal_v1_2_0",
            "v1_0_equal_v1_0",
            "v1_2_3_equal_v1_2_3",
            "single_component_equal_to_three",
            "three_components_equal_to_single",
            "v2_greater_than_v1",
            "v1_less_than_v2",
            "v1_2_3_less_than_v1_2_4",
            "v1_2_5_greater_than_v1_2_4",
            "two_components_equal_three_with_zeros",
            "three_with_zeros_equal_two",
        ],
    )
    def test_version_compare_returns_correct_result(self, a: str, b: str, expected: int):
        assert _version_compare(a, b) == expected

    @pytest.mark.parametrize(
        "a, expected",
        [
            ("v1.0.0", 1),
            ("v1.10.0", 1),
            ("v0.0.1", 1),
        ],
        ids=[
            "v1_0_0_greater_than_none",
            "v1_10_0_greater_than_none",
            "v0_0_1_greater_than_none",
        ],
    )
    def test_version_compare_greater_than_none(self, a: str, expected: int):
        assert _version_compare(a, None) == expected
