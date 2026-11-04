from agent.verification.citation import check_quote, needs_quote

SRC = {"guide": {"kind": "pdf", "pages": ["The double-wall vacuum body keeps drinks cold for up to 24 hours\nand hot for up to 12 hours.", "Hand wash the body."]}}


def q(text, page=1, sid="guide"):
    return {"source_id": sid, "page": page, "quote": text}


def test_exact_quote_across_line_break_passes():
    assert check_quote(q("keeps drinks cold for up to 24 hours and hot"), SRC, 15) is None


def test_paraphrase_inside_quote_is_refused():
    assert "not on guide page 1" in check_quote(q("keeps drinks cold all day long"), SRC, 15)


def test_wrong_page_points_to_right_page():
    assert "page 2" in check_quote(q("Hand wash the body", page=1), SRC, 15)


def test_short_quote_refused():
    assert "at least" in check_quote(q("cold"), SRC, 15)


def test_unknown_source_and_page():
    assert "does not exist" in check_quote(q("keeps drinks cold for up", sid="x"), SRC, 15)
    assert "out of range" in check_quote(q("keeps drinks cold for up", page=9), SRC, 15)


def test_cover_lines_need_quotes_only_with_numbers():
    assert not needs_quote("cover", "Drink more water at work")
    assert needs_quote("cover", "Cold for 24 hours")
    assert needs_quote("point", "Made of steel")


def test_numbers_must_be_in_quotes():
    from agent.verification.citation import number_gaps
    q = [{"quote": "launch price is 28,000 won until November 30"}]
    assert number_gaps("Launch price 28,000 won until Nov 30", q) == []
    assert number_gaps("Launch price 25,000 won", q) == ["25,000"]
    assert number_gaps("18/8 steel", [{"quote": "made of 18/8 stainless steel"}]) == []
