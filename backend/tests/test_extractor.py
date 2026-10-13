from app.scraping.extractor import (
    MIN_TEXT_CHARS,
    extract_text,
    is_thin,
    normalize_text,
)

ARTICLE = """
<html><head><title>Blog</title></head><body>
<nav><a href="/">Home</a> <a href="/pricing">Pricing</a>
<a href="/login">Login</a></nav>
<article>
  <h1>Acme launches a new analytics dashboard</h1>
  <p>Acme announced today that its analytics dashboard is now available to every
  customer on all plans. The release includes real-time reports, custom filters and
  an export feature that many users had requested for a long time.</p>
  <p>According to the company, the dashboard reduces the time needed to build a
  weekly report from several hours to a few minutes, and it integrates with the
  most popular data warehouses without any additional configuration.</p>
</article>
<footer>Copyright Acme. All rights reserved. Cookie settings.</footer>
</body></html>
""".encode()


def test_extract_keeps_article_and_drops_boilerplate():
    text = extract_text(ARTICLE)
    assert text is not None
    assert "analytics dashboard" in text
    assert "Cookie settings" not in text
    assert "Login" not in text


def test_noscript_content_is_removed():
    html = ARTICLE.replace(
        b"<footer>",
        b"<noscript>Enable JavaScript to see this unique notice</noscript><footer>",
    )
    text = extract_text(html)
    assert text is not None
    assert "unique notice" not in text


def test_extract_handles_windows_1251_bytes():
    body = (
        "<html><head><meta charset='windows-1251'></head><body><article><p>"
        + "Добро пожаловать в официальную службу регистрации доменных имен. " * 8
        + "</p></article></body></html>"
    ).encode("cp1251")
    text = extract_text(body)
    assert text is not None
    assert "Добро пожаловать" in text


def test_extract_returns_thin_for_js_shell():
    shell = b"<html><body><div id='root'></div><script></script></body></html>"
    assert is_thin(extract_text(shell))


def test_normalize_text():
    assert normalize_text("  a \n\t b c  ") == "a b c"
    assert normalize_text("ﬁx") == "fix"  # NFKC ligature


def test_is_thin():
    assert is_thin(None)
    assert is_thin("")
    assert is_thin("x" * (MIN_TEXT_CHARS - 1))
    assert not is_thin("x" * MIN_TEXT_CHARS)
