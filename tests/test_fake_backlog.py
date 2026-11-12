"""Guards the shared fixture, so the counters in the test plan stay true."""


def test_fake_backlog_matches_the_test_plan(fake_backlog):
    estimated = [t for t in fake_backlog if t["story_points"] is not None]
    unestimated = [t for t in fake_backlog if t["story_points"] is None]

    assert len(fake_backlog) == 12
    assert len(unestimated) == 8
    assert len(estimated) == 4
    assert sum(t["story_points"] for t in estimated) == 16


def test_fake_backlog_keys_are_unique_and_ranked(fake_backlog):
    keys = [t["key"] for t in fake_backlog]
    ranks = [t["rank"] for t in fake_backlog]

    assert len(set(keys)) == len(keys)
    assert ranks == sorted(ranks)
