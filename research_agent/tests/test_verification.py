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


# --- syndication dedupe ---------------------------------------------------------------

from research_agent.verification import independent_groups, near_duplicate, shingles  # noqa: E402

STORY = ("Veltrava Rail Components has recalled about 1,800 door actuators after a sensor fault was found. "
         "Replacement parts will be delivered to operators by December, the company said on Tuesday.")


def test_syndicated_copy_with_extra_boilerplate_is_near_duplicate():
    copy = "Rail News Daily | Home | Subscribe\n" + STORY + "\nRead more stories about rolling stock."
    assert near_duplicate(shingles(STORY), shingles(copy))


def test_different_reports_of_same_event_are_independent():
    other = ("Operators were told on Tuesday that Veltrava will replace a batch of faulty door actuators; "
             "a spokesperson said the sensor problem affects roughly 1,800 units built last year.")
    assert not near_duplicate(shingles(STORY), shingles(other))


def test_independent_groups_merge_same_domain_and_copies():
    a = ("reuters.com", shingles(STORY))
    b = ("reuters.com", shingles("A completely different Reuters article about something else entirely today."))
    c = ("railnews.example", shingles("Header\n" + STORY))
    d = ("dw.com", shingles("Deutsche Welle reports a separate strike at the plant, unrelated wording here."))
    groups = independent_groups([a, b, c, d])
    assert len(groups) == 2  # {a, b (same domain), c (copy of a)} and {d}


def test_shared_25_word_passage_means_copy_even_with_different_framing():
    from research_agent.verification import COPY_PASSAGE_WORDS
    passage = ("the federal cartel office said on tuesday that veltrava rail components had agreed prices for brake "
               "pads with a competitor between 2019 and 2021 and imposed a fine of four point two million euro today")
    a = "Rail News. " + passage + " More text about other suppliers and market outlook for the coming years in Europe."
    b = ("Completely different introduction written by our own reporter with new details from the court. "
         + passage + " The company said it would appeal and declined further comment on Thursday afternoon.")
    s5a, s5b = shingles(a), shingles(b)
    assert not near_duplicate(s5a, s5b)  # different enough overall ...
    groups = independent_groups([("x.example", s5a), ("y.example", s5b)],
                                passages=[shingles(a, COPY_PASSAGE_WORDS), shingles(b, COPY_PASSAGE_WORDS)])
    assert len(groups) == 1  # ... but a shared 25-word passage makes them one source
    short = passage.split()[:20]
    c = "Other words entirely here. " + " ".join(short) + " and then something new follows here."
    groups = independent_groups([("x.example", s5a), ("z.example", shingles(c))],
                                passages=[shingles(a, COPY_PASSAGE_WORDS), shingles(c, COPY_PASSAGE_WORDS)])
    assert len(groups) == 2  # 20 shared words is not a copy
