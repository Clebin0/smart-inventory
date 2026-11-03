from __future__ import annotations

from datetime import datetime, timezone


def _utc(value: datetime) -> datetime:
    """Treat naive database timestamps as UTC and normalize aware values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def score_asset(
    asset,
    movement_count: int = 0,
    last_movement: datetime | None = None,
) -> dict[str, object]:
    """Apply the lab's lifecycle rules and return the score with its causes."""
    score = 0
    reasons: list[str] = []

    status = getattr(asset, "status", None)
    assigned_to = getattr(asset, "assigned_to", None)

    if status == "maintenance":
        score += 35
        reasons.append("Ativo em manutenção")

    if status == "in_use" and not assigned_to:
        score += 30
        reasons.append("Ativo em uso sem responsável")

    if not getattr(asset, "serial_number", None):
        score += 10
        reasons.append("Número de série não informado")

    if not getattr(asset, "location", None):
        score += 10
        reasons.append("Localização não informada")

    created_at = getattr(asset, "created_at", None)
    if created_at:
        age_days = (datetime.now(timezone.utc) - _utc(created_at)).days
        if age_days > 1095:
            score += 15
            reasons.append("Cadastro com mais de três anos")

    if movement_count >= 12:
        score += 10
        reasons.append("Doze ou mais movimentações registradas")

    if status == "maintenance" and last_movement:
        days_in_current_state = (
            datetime.now(timezone.utc) - _utc(last_movement)
        ).days
        if days_in_current_state > 14:
            score += 25
            reasons.append("Mais de 14 dias sem movimentação durante a manutenção")

    score = min(score, 100)
    if score >= 60:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"

    return {
        "score": score,
        "level": level,
        "reasons": reasons or ["Nenhum sinal de atenção identificado pelas regras atuais"],
    }
