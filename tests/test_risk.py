from risk_engine import score_asset

class Fake:
    status="in_use"
    assigned_to=None
    serial_number=None
    location="CWB"
    created_at=None

def test_risk_score_is_explainable():
    result=score_asset(Fake(),movement_count=15,last_movement=None)
    assert result["score"]>=40
    assert result["level"] in {"medium","high"}
    assert result["reasons"]
