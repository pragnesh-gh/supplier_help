from research_agent.verification import normalize, quote_in_text, trim_quote, word_count

PAGE = """Knorr-Bremse AG said on Tuesday that the Federal Cartel Office
imposed a fine of EUR 12.5 million — citing “coordinated pricing” in the
brake-pad market between 2019 and 2021."""


def test_normalize_collapses_whitespace_case_and_quotes():
    assert normalize("  Hello\n\tWORLD “x” ’y’ — z ") == "hello world \"x\" 'y' - z"


def test_exact_quote_found_despite_line_breaks_and_case():
    assert quote_in_text("the federal cartel office imposed a fine of EUR 12.5 million", PAGE)


def test_quote_with_minor_punctuation_difference_found():
    assert quote_in_text('citing "coordinated pricing" in the brake-pad market', PAGE)
    assert quote_in_text("Knorr-Bremse AG said on Tuesday, that the Federal Cartel Office", PAGE)


def test_fabricated_quote_rejected():
    assert not quote_in_text("the Federal Cartel Office imposed a fine of EUR 125 million", PAGE)
    assert not quote_in_text("Knorr-Bremse filed for insolvency", PAGE)


def test_empty_or_tiny_quote_rejected():
    assert not quote_in_text("", PAGE)
    assert not quote_in_text("the", PAGE)


def test_ellipsis_quote_requires_every_part_in_order():
    assert quote_in_text("Federal Cartel Office ... coordinated pricing", PAGE)
    assert not quote_in_text("coordinated pricing ... Federal Cartel Office", PAGE)


def test_trim_quote_caps_25_words():
    long = " ".join(f"w{i}" for i in range(40))
    assert word_count(trim_quote(long)) <= 26  # 25 words + ellipsis marker
    assert trim_quote("short quote") == "short quote"
