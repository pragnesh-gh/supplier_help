"""Source classification: trusted (allowlist), unverified (any other site), denylisted (never used)."""

import pytest

from research_agent.config import ConfigError, load_allowlist


@pytest.fixture(scope="module")
def allow():
    return load_allowlist().with_company("veltrava-rail.example", "Veltrava Rail Components GmbH")


def test_allowlisted_is_trusted(allow):
    m = allow.classify("https://www.reuters.com/x")
    assert m.trust == "trusted" and m.tier == "major_news"
    assert allow.classify("https://veltrava-rail.example/ir").tier == "company_own"


def test_unknown_site_is_unverified(allow):
    m = allow.classify("https://rail-insider.example/post")
    assert m.trust == "unverified" and m.tier == "open_web" and m.publisher == "rail-insider.example"
    assert allow.rank(m) > max(allow.priority.values())  # always after every trusted tier


@pytest.mark.parametrize("url", ["https://www.reddit.com/r/x", "https://old.reddit.com/r/x", "https://x.com/a",
                                 "https://www.prnewswire.com/news", "https://en.wikipedia.org/wiki/X",
                                 "https://pastebin.com/abc", "https://docs.publicnow.com/1D57F4457352428E"])
def test_denylisted_sites_are_dropped(allow, url):
    assert allow.classify(url) is None
    assert allow.denied_category(url) is not None


def test_non_http_urls_are_dropped(allow):
    assert allow.classify("ftp://reuters.com/x") is None


def test_denylisted_company_site_is_not_trusted():
    a = load_allowlist().with_company("linkedin.com", "Some Co")
    assert a.tiers["company_own"] == {} and a.classify("https://linkedin.com/company/x") is None


def test_domain_both_trusted_and_denied_is_a_config_error(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text("tiers:\n  official:\n    domains: {reddit.com: R}\ndenylist:\n  forums: [reddit.com]\n")
    with pytest.raises(ConfigError):
        load_allowlist(p)
