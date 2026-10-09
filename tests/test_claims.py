"""Module 2 tests (offline: LLM and network are mocked)."""
from claims import extract, numeric, rules, verify
from common.models import Claim, ContentBundle, Evidence, Verdict


def test_rules_tag_numeric_attribution_hindi():
    score, kind, qs = rules.tag("सरकार के अनुसार 80 करोड़ लोगों को मुफ्त राशन मिल रहा है।")
    assert kind == "numeric" and score >= 0.5 and qs == ["80 करोड़"]


def test_rules_drop_opinions_and_questions():
    assert rules.candidates("I think we should all subscribe. Is it true?", "caption") == []


def test_rules_keep_attribution_with_number():
    c = rules.candidates("According to WHO, 45% of children are anaemic. Like and share!", "caption")
    assert len(c) == 1 and c[0]["kind"] == "numeric"


def test_numeric_parse_indian_units():
    assert numeric.parse("₹2 lakh crore") == [(2e12, "count")]
    assert numeric.parse("२० करोड़") == [(2e8, "count")]
    assert numeric.parse("grew 7.8%") == [(7.8, "percent")]
    assert numeric.parse("in 2024") == []  # bare years are not quantities


def test_numeric_compare():
    assert "matches" in numeric.compare("unemployment is 7.8%", ["rate stood at 7.8 per cent"])
    assert "not found" in numeric.compare("unemployment is 12%", ["rate stood at 7.8 per cent"])
    assert numeric.compare("no numbers here", ["7%"]) == ""


def test_verdict_without_evidence_is_downgraded():
    v = Verdict("supported", "looks right", evidence=[])
    assert v.label == "unverifiable"


def test_verify_no_evidence_is_unverifiable():
    v = verify.verify(Claim(text="x"), [])
    assert v.label == "unverifiable" and v.method == "none"


def test_rating_to_label():
    assert verify.rating_to_label("False") == "contradicted"
    assert verify.rating_to_label("Untrue") == "contradicted"
    assert verify.rating_to_label("Missing Context") == "conflicting"
    assert verify.rating_to_label("True") == "supported"
    assert verify.rating_to_label("Explainer") is None


def _ev(n=2):
    return [Evidence(url=f"https://ex.com/{i}", title=f"t{i}", snippet="s", source_type="news") for i in range(n)]


def test_llm_verdict_keeps_only_valid_citations(monkeypatch):
    monkeypatch.setattr(verify.llm, "available", lambda: True)
    monkeypatch.setattr(verify.llm, "chat_json", lambda *a, **k: {
        "label": "contradicted", "rationale": "See [E2].", "cited": ["E2", "E9"], "confidence": 0.8})
    v = verify.verify(Claim(text="claim"), _ev(2))
    assert v.label == "contradicted" and [e.url for e in v.evidence] == ["https://ex.com/1"]


def test_llm_verdict_without_citations_becomes_unverifiable(monkeypatch):
    monkeypatch.setattr(verify.llm, "available", lambda: True)
    monkeypatch.setattr(verify.llm, "chat_json", lambda *a, **k: {
        "label": "supported", "rationale": "trust me", "cited": [], "confidence": 0.9})
    v = verify.verify(Claim(text="claim"), _ev(2))
    assert v.label == "unverifiable"


def test_extract_falls_back_to_rules_when_llm_fails(monkeypatch):
    monkeypatch.setattr(extract.llm, "available", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(extract.llm, "chat_json", boom)
    b = ContentBundle(url="u", platform="x", caption="The government said 500 new schools opened in 2025.")
    claims, method = extract.extract_claims(b)
    assert method == "rules" and len(claims) == 1


def test_extract_llm_output_parsed(monkeypatch):
    monkeypatch.setattr(extract.llm, "available", lambda: True)
    monkeypatch.setattr(extract.llm, "chat_json", lambda *a, **k: {"claims": [
        {"text": "शहर का 50% पानी दूषित है", "text_en": "50% of the city's water is polluted", "kind": "numeric", "source": "ocr", "queries": ["q1"]},
        {"text": ""}]})
    claims, method = extract.extract_claims(ContentBundle(url="u", platform="x", caption="anything"))
    assert method == "llm" and len(claims) == 1 and claims[0].queries == ["q1"] and claims[0].source == "ocr"


# --- regressions from the DD News G20 example run (9 Oct 2026) ---
def test_junk_fragments_are_not_claims():
    for junk in ["Date:  11/09/2023", "@PIBFactCheck", "OVER र४१०० cr"]:
        assert rules.is_junk(junk.translate(rules._DEV_DIGITS)), junk
    assert not rules.is_junk("Modi Govt spent 300% more on G20 than the funds allocated in budget")


def test_devanagari_digits_normalised_in_candidates():
    c = rules.candidates("Modi Govt spent a WHOPPING ३००% more on G२० than the funds allocated", "ocr")
    assert c and "300%" in c[0]["text"]


def test_youtube_description_boilerplate_ranked_out():
    b = ContentBundle(url="u", platform="youtube", title="PIB fact check denies claim of govt spending 300% more on G20",
                      caption="Launched in 2003, DD News has made a name for itself to deliver balanced news.")
    claims, _ = extract.extract_claims(b)
    assert [c.source for c in claims] == ["title"]


def test_nli_ignores_loosely_related_evidence(monkeypatch):
    monkeypatch.setattr(verify, "nli_scores", lambda p, h: {"contradiction": 0.99, "entailment": 0.0})
    ev = [Evidence(url="https://ex.com/x", title="unrelated", snippet="s", source_type="factcheck", score=0.80)]
    assert verify._verify_nli(Claim(text="some claim about G20 spending"), ev).label == "unverifiable"
