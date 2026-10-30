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
