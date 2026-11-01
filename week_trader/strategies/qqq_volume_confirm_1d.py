from __future__ import annotations


class VolumeConfirmSignalError(Exception):
    pass


def evaluate_qqq_volume_confirm_1d(
    closes: list[float],
    volumes: list[float],
    *,
    hypothesis_id: str,
    volume_lookback: int = 20,
    volume_multiple: float = 1.5,
) -> dict[str, object]:
    """
    High-volume confirmation (Campbell, Grossman & Wang 1993): long QQQ when the
    latest session volume exceeds volume_multiple × trailing average and return > 0.
    """
    if len(closes) < volume_lookback + 2 or len(volumes) < volume_lookback + 2:
        raise VolumeConfirmSignalError(
            f"need {volume_lookback + 2} closes and volumes for volume confirm"
        )
    if closes[-2] <= 0:
        raise VolumeConfirmSignalError("invalid prior close")
    session_return = closes[-1] / closes[-2] - 1.0
    vol_window = volumes[-(volume_lookback + 1) : -1]
    avg_vol = sum(vol_window) / len(vol_window)
    today_vol = volumes[-1]
    high_volume = today_vol >= volume_multiple * avg_vol if avg_vol > 0 else False
    side = "long" if high_volume and session_return > 0 else "flat"
    return {
        "strategy": hypothesis_id,
        "symbol": "QQQ",
        "side": side,
        "signal_family": "volume_return_confirm",
        "session_return": session_return,
        "volume_today": today_vol,
        "volume_avg": avg_vol,
        "volume_multiple": volume_multiple,
        "last_close": closes[-1],
    }
