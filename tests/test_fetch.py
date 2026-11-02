from datetime import datetime

import common
import fetch

RSS = """<?xml version="1.0"?><rss><channel><title>t</title>
<item><title><![CDATA[ New  model ]]></title><link>https://example.com/a</link><pubDate>Thu, 29 Oct 2026 17:00:00 GMT</pubDate></item>
<item><title>No date</title><link>https://example.com/b</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom post</title><link href="https://example.com/c"/><updated>2026-10-30T01:00:00Z</updated></entry>
</feed>"""


def test_parse_rss_converts_to_kst():
    a, b = fetch.parse_feed(RSS)
    assert a["title"] == "New model" and a["url"] == "https://example.com/a"
    assert a["published"] == datetime(2026, 10, 30, 2, 0, tzinfo=common.KST)
    assert b["published"] is None


def test_parse_atom():
    (c,) = fetch.parse_feed(ATOM)
    assert c["url"] == "https://example.com/c"
    assert c["published"].isoformat() == "2026-10-30T10:00:00+09:00"


def test_html_to_text_drops_scripts_and_keeps_blocks():
    html = "<html><head><title>x</title></head><body><script>evil()</script><h1>제목</h1><p>첫  문단</p><div>둘째<br>줄</div></body></html>"
    assert fetch.html_to_text(html) == "제목\n첫 문단\n둘째\n줄"


def test_unzip_handles_unmarked_gzip():
    import gzip
    assert fetch._unzip(gzip.compress("<rss/>".encode())) == b"<rss/>"
    assert fetch._unzip(b"<rss/>") == b"<rss/>"


def test_date_patterns_cover_window():
    import re
    pat = re.compile(fetch.date_patterns(datetime(2026, 10, 30, 7, 23, tzinfo=common.KST), datetime(2026, 11, 1, 7, 23, tzinfo=common.KST)))
    for text in ("October 30, 2026", "Oct 31, 2026", "November 1, 2026", "Nov 01 2026", "2026-11-01", "2026.10.31"):
        assert pat.search(text), text
    for text in ("October 29, 2026", "2026-11-02"):
        assert not pat.search(text), text


def test_window_since_last_run(tmp_path):
    import json
    runs = tmp_path / "runs"
    runs.mkdir()
    sec = {"window": {"since_last_run": True, "hours": 24, "max_days": 8}}
    now = datetime(2026, 11, 7, 8, 0, tzinfo=common.KST)
    assert common.window_since(sec, now, tmp_path) == datetime(2026, 11, 6, 8, 0, tzinfo=common.KST)
    for day, status in (("2026-10-31", "published"), ("2026-11-06", "failed"), ("2026-11-07", "empty")):
        (runs / f"{day}.json").write_text(json.dumps({"date": day, "started_at": f"{day}T08:00:00+09:00", "status": status}))
    assert common.window_since(sec, now, tmp_path) == datetime(2026, 10, 31, 8, 0, tzinfo=common.KST)
    sec["window"]["max_days"] = 3
    assert common.window_since(sec, now, tmp_path) == datetime(2026, 11, 4, 8, 0, tzinfo=common.KST)
