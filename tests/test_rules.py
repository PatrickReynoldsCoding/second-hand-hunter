from hunter.listing import Listing
from hunter.rules import avoid_hits, measurements_cm, no_ai_verdict, text_reject
from hunter.spec import Hunt

SOFA = Hunt(slug="sofa", name="Corner sofa", searches=["corner sofa"], max_price=100, max_distance=10,
            sites=["gumtree"], size={"width_max": 200, "chaise_max": 200}, avoid=["leather"],
            musts=["Chaise on the right when sitting"])


def listing(title="Corner sofa", description=""):
    return Listing(site="gumtree", site_id="1", url="u", title=title, price=50, description=description)


def test_measurements_in_many_forms():
    assert measurements_cm("Width 246cm") == [246]
    assert measurements_cm("2.4m wide") == [240]
    assert measurements_cm("W 210 x D 90 x H 85 cm") == [210, 90, 85]
    assert measurements_cm("200cm x 150cm") == [200, 150]
    assert measurements_cm("8ft long") == [243.8]
    assert measurements_cm("6'6\" long") == [198.1]
    assert measurements_cm("2 seater, 3 cushions, 15 years old") == []


def test_avoid_words():
    assert avoid_hits(SOFA, "Cream LEATHER corner sofa") == ["leather"]
    assert avoid_hits(SOFA, "Faux leather finish") == ["leather"]
    assert avoid_hits(SOFA, "Fabric, not leather") == []
    assert avoid_hits(SOFA, "Grey fabric") == []


def test_text_reject():
    assert "leather" in text_reject(SOFA, listing("Leather corner sofa"))
    assert "246" in text_reject(SOFA, listing(description="It is 246cm wide"))
    assert text_reject(SOFA, listing(description="190cm x 160cm, grey fabric")) is None


def test_no_ai_verdict_asks_for_sizes_only_when_missing():
    reason, question = no_ai_verdict(SOFA, listing())
    assert "Not checked: Chaise on the right" in reason and "measurements" in question
    _, question = no_ai_verdict(SOFA, listing(description="190 x 160 cm"))
    assert question == ""
