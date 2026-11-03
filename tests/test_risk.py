from risk_engine import score_asset


class FakeAsset:
    status = "in_use"
    assigned_to = None
    serial_number = None
    location = "CWB"
    created_at = None


def test_score_lists_the_conditions_that_need_attention():
    result = score_asset(
        FakeAsset(),
        movement_count=15,
        last_movement=None,
    )

    assert result["score"] >= 40
    assert result["level"] in {"medium", "high"}
    assert "Ativo em uso sem responsável" in result["reasons"]
    assert "Número de série não informado" in result["reasons"]
    assert "Doze ou mais movimentações registradas" in result["reasons"]
