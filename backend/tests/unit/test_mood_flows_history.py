"""
mood_v2 flows-history tests (MOOD_IMPROVEMENT_PLAN §11.3).

`cache_market_flows` keeps a rolling per-day list of raw FII/DII/PCR values in
Redis (newest first, same-day re-run replaces the head) and `get_flows_5d_means`
returns the mean of the last ≤ 5 entries — the smoothed inputs the mood_v2
normalizers expect. Redis failures must degrade (shorter mean / all-None), never
raise into the snapshot pipeline.
"""

from __future__ import annotations

import json

from dhanradar.mood import service


class _FakeRedis:
    """Minimal async Redis stub covering the list ops the flows history uses."""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    async def set(self, key, value, ex=None):
        self.kv[key] = value

    async def lindex(self, key, idx):
        rows = self.lists.get(key, [])
        return rows[idx] if -len(rows) <= idx < len(rows) else None

    async def lset(self, key, idx, value):
        self.lists[key][idx] = value

    async def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    async def ltrim(self, key, start, stop):
        self.lists[key] = self.lists.get(key, [])[start : stop + 1]

    async def lrange(self, key, start, stop):
        return self.lists.get(key, [])[start : stop + 1]

    async def expire(self, key, ttl):
        pass


def _patch_redis(monkeypatch) -> _FakeRedis:
    fake = _FakeRedis()
    monkeypatch.setattr("dhanradar.redis_client.get_redis", lambda: fake)
    return fake


async def test_cache_market_flows_appends_one_entry_per_day(monkeypatch):
    fake = _patch_redis(monkeypatch)
    await service.cache_market_flows({"fii_flows": 1000.0, "dii_flows": 500.0, "put_call_ratio": 1.1})
    # Same-day second run (twice-daily snapshots) REPLACES the head, no duplicate.
    await service.cache_market_flows({"fii_flows": 2000.0, "dii_flows": 700.0, "put_call_ratio": 0.9})

    rows = fake.lists[service._FLOWS_HISTORY_KEY]
    assert len(rows) == 1
    head = json.loads(rows[0])
    assert head["fii"] == 2000.0 and head["pcr"] == 0.9
    # The 'last' cache for the public /market/flows endpoint is still written.
    assert service._FLOWS_CACHE_KEY in fake.kv


async def test_get_flows_5d_means_averages_last_five(monkeypatch):
    fake = _patch_redis(monkeypatch)
    # 7 days of history, newest first — only the first 5 should count.
    for i, fii in enumerate([1000, 2000, 3000, 4000, 5000, 90000, 90000]):
        fake.lists.setdefault(service._FLOWS_HISTORY_KEY, []).append(
            json.dumps({"d": f"2026-08-{10 + i}", "fii": fii, "dii": fii / 2, "pcr": 1.0})
        )
    means = await service.get_flows_5d_means()
    assert means["fii"] == 3000.0
    assert means["dii"] == 1500.0
    assert means["pcr"] == 1.0


async def test_get_flows_5d_means_skips_missing_keys_never_imputes(monkeypatch):
    fake = _patch_redis(monkeypatch)
    fake.lists[service._FLOWS_HISTORY_KEY] = [
        json.dumps({"d": "2026-08-16", "fii": 1000.0, "dii": None, "pcr": None}),
        json.dumps({"d": "2026-08-15", "fii": 3000.0, "dii": None, "pcr": 1.2}),
    ]
    means = await service.get_flows_5d_means()
    assert means["fii"] == 2000.0   # mean over the days present
    assert means["dii"] is None     # no entry carries dii → absent, not 0
    assert means["pcr"] == 1.2


async def test_get_flows_5d_means_redis_failure_returns_all_none(monkeypatch):
    class _Broken:
        async def lrange(self, *_a):
            raise ConnectionError("redis down")

    monkeypatch.setattr("dhanradar.redis_client.get_redis", lambda: _Broken())
    means = await service.get_flows_5d_means()
    assert means == {"fii": None, "dii": None, "pcr": None}
