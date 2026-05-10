"""Blink + gaze + vergence + cat pupil focus (slit relaxed ↔ dilated engaged).

Blink repertoire: normal bilateral, slow bilateral (relaxed / “slow blink” cat contentment),
double-blink pair, wink (one eye). Engaged cats use faster saccades; attention spikes snap gaze.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

from eyes_draw import EyePose

WinkSide = Literal["none", "left", "right"]


class _BlinkPhase(Enum):
    IDLE = auto()
    CLOSING = auto()
    OPENING = auto()


@dataclass
class EyeAnimatorConfig:
    blink_interval_min_s: float = 2.5
    blink_interval_max_s: float = 5.0
    blink_close_duration_s: float = 0.09
    blink_open_duration_s: float = 0.11
    slow_close_duration_s: float = 0.26
    slow_open_duration_s: float = 0.34
    double_gap_min_s: float = 0.12
    double_gap_max_s: float = 0.22
    # Mutually exclusive weights when a blink is due (must sum ≤ 1).
    slow_blink_probability: float = 0.12
    double_blink_probability: float = 0.16
    wink_probability: float = 0.07
    # When pupil_focus is low (relaxed), prefer slow cat-like blinks more often.
    relaxed_focus_threshold: float = 0.14
    slow_blink_when_relaxed_probability: float = 0.42
    gaze_transition_min_s: float = 0.2
    gaze_transition_max_s: float = 0.4
    gaze_transition_engaged_min_s: float = 0.04
    gaze_transition_engaged_max_s: float = 0.095
    gaze_dwell_min_s: float = 1.0
    gaze_dwell_max_s: float = 2.2
    gaze_targets: tuple[tuple[float, float, float], ...] = (
        (0.0, 0.0, 0.0),
        (-0.85, 0.0, 0.0),
        (0.85, 0.0, 0.0),
        (0.0, 0.75, 0.0),
        (0.0, -0.75, 0.0),
        (0.0, 0.0, 0.65),
        (0.1, 0.05, 0.55),
    )
    focus_rise_s: float = 0.07
    focus_fall_s: float = 1.35
    focus_target_decay_s: float = 3.5
    attention_spike_probability: float = 0.0025


class EyeAnimator:
    """Emits EyePose for cartoon cat eyes (slit ↔ round pupils)."""

    def __init__(self, rng: random.Random, cfg: EyeAnimatorConfig | None = None) -> None:
        self._rng = rng
        self._cfg = cfg or EyeAnimatorConfig()
        self._t = 0.0
        self._next_blink_at = self._schedule_next_blink()
        self._blink_phase = _BlinkPhase.IDLE
        self._blink_t0 = 0.0
        self._close_dur = self._cfg.blink_close_duration_s
        self._open_dur = self._cfg.blink_open_duration_s
        self._wink_side: WinkSide = "none"
        self._will_chain_double = False
        self._pending_second_double = False
        self._gx = 0.0
        self._gy = 0.0
        self._gc = 0.0
        self._gx_tar = 0.0
        self._gy_tar = 0.0
        self._gc_tar = 0.0
        self._gaze_move_until = 0.0
        self._gaze_dwell_until = 0.0
        self._gaze_transition_len = 0.35
        self._gaze_move_start_t = 0.0
        self._gx0 = 0.0
        self._gy0 = 0.0
        self._gc0 = 0.0
        self._focus = 0.0
        self._focus_tar = 0.0
        self._pick_new_gaze_target()

    def _schedule_next_blink(self) -> float:
        dt = self._rng.uniform(self._cfg.blink_interval_min_s, self._cfg.blink_interval_max_s)
        return self._t + dt

    def _gaze_engaged(self) -> bool:
        return self._focus > 0.38 or self._focus_tar > 0.32

    def _pick_new_gaze_target(self, *, engaged: bool | None = None) -> None:
        self._gx0, self._gy0, self._gc0 = self._gx, self._gy, self._gc
        choice = self._rng.choice(self._cfg.gaze_targets)
        self._gx_tar, self._gy_tar, self._gc_tar = choice
        if engaged is None:
            engaged = self._gaze_engaged()
        if engaged:
            lo, hi = (
                self._cfg.gaze_transition_engaged_min_s,
                self._cfg.gaze_transition_engaged_max_s,
            )
        else:
            lo, hi = self._cfg.gaze_transition_min_s, self._cfg.gaze_transition_max_s
        self._gaze_transition_len = self._rng.uniform(lo, hi)
        self._gaze_move_start_t = self._t
        self._gaze_move_until = self._t + self._gaze_transition_len
        dwell = self._rng.uniform(self._cfg.gaze_dwell_min_s, self._cfg.gaze_dwell_max_s)
        self._gaze_dwell_until = self._gaze_move_until + dwell

    def _snap_gaze_attention(self) -> None:
        """Fast saccade toward a new target when something engages attention."""
        self._pick_new_gaze_target(engaged=True)

    def _arm_blink_from_idle(self) -> None:
        """Configure durations and wink/double flags when starting CLOSING."""
        if self._pending_second_double:
            self._pending_second_double = False
            self._close_dur = self._cfg.blink_close_duration_s
            self._open_dur = self._cfg.blink_open_duration_s
            self._wink_side = "none"
            self._will_chain_double = False
            return

        # Relaxed cat: slow blink (contentment) more likely when pupils are slit / calm.
        if self._focus < self._cfg.relaxed_focus_threshold:
            if self._rng.random() < self._cfg.slow_blink_when_relaxed_probability:
                self._wink_side = "none"
                self._close_dur = self._cfg.slow_close_duration_s
                self._open_dur = self._cfg.slow_open_duration_s
                self._will_chain_double = False
                return

        p_w = self._cfg.wink_probability
        p_s = self._cfg.slow_blink_probability
        p_d = self._cfg.double_blink_probability
        u = self._rng.random()

        if u < p_w:
            self._wink_side = self._rng.choice(("left", "right"))
            self._close_dur = self._cfg.blink_close_duration_s
            self._open_dur = self._cfg.blink_open_duration_s
            self._will_chain_double = False
        elif u < p_w + p_s:
            self._wink_side = "none"
            self._close_dur = self._cfg.slow_close_duration_s
            self._open_dur = self._cfg.slow_open_duration_s
            self._will_chain_double = False
        elif u < p_w + p_s + p_d:
            self._wink_side = "none"
            self._close_dur = self._cfg.blink_close_duration_s
            self._open_dur = self._cfg.blink_open_duration_s
            self._will_chain_double = True
        else:
            self._wink_side = "none"
            self._close_dur = self._cfg.blink_close_duration_s
            self._open_dur = self._cfg.blink_open_duration_s
            self._will_chain_double = False

    def advance(self, dt: float) -> EyePose:
        self._t += dt
        self._update_blink()
        self._update_gaze()
        self._update_focus(dt)
        b = self._blink_amount()
        if self._wink_side == "left":
            bl, br = b, 0.0
        elif self._wink_side == "right":
            bl, br = 0.0, b
        else:
            bl, br = b, b
        return EyePose(
            blink_close_left=max(0.0, min(1.0, bl)),
            blink_close_right=max(0.0, min(1.0, br)),
            gaze_x=self._gx,
            gaze_y=self._gy,
            convergence=max(0.0, min(1.0, self._gc)),
            pupil_focus=max(0.0, min(1.0, self._focus)),
        )

    def _update_focus(self, dt: float) -> None:
        stim = self._cfg.attention_spike_probability * max(dt * 60.0, 1.0)
        if self._rng.random() < stim:
            self._focus_tar = max(self._focus_tar, self._rng.uniform(0.92, 1.0))
            self._snap_gaze_attention()

        tau_tar = max(self._cfg.focus_target_decay_s, 1e-3)
        a_tar = min(1.0, dt / tau_tar)
        self._focus_tar += (0.0 - self._focus_tar) * a_tar

        delta = self._focus_tar - self._focus
        tau = self._cfg.focus_rise_s if delta > 0 else self._cfg.focus_fall_s
        tau = max(tau, 1e-3)
        self._focus += delta * min(1.0, dt / tau)

    def _blink_amount(self) -> float:
        if self._blink_phase == _BlinkPhase.IDLE:
            return 0.0
        if self._blink_phase == _BlinkPhase.CLOSING:
            elapsed = self._t - self._blink_t0
            dur = self._close_dur
            return max(0.0, min(1.0, elapsed / dur)) if dur > 0 else 1.0
        elapsed = self._t - self._blink_t0
        dur = self._open_dur
        return max(0.0, min(1.0, 1.0 - elapsed / dur)) if dur > 0 else 0.0

    def _update_blink(self) -> None:
        if self._blink_phase == _BlinkPhase.IDLE:
            if self._t >= self._next_blink_at:
                self._arm_blink_from_idle()
                self._blink_phase = _BlinkPhase.CLOSING
                self._blink_t0 = self._t
            return

        if self._blink_phase == _BlinkPhase.CLOSING:
            if self._blink_amount() >= 1.0:
                self._blink_phase = _BlinkPhase.OPENING
                self._blink_t0 = self._t
            return

        if self._blink_amount() <= 0.0:
            self._blink_phase = _BlinkPhase.IDLE
            if self._will_chain_double:
                self._will_chain_double = False
                self._pending_second_double = True
                gap = self._rng.uniform(self._cfg.double_gap_min_s, self._cfg.double_gap_max_s)
                self._next_blink_at = self._t + gap
            else:
                self._next_blink_at = self._schedule_next_blink()

    def _update_gaze(self) -> None:
        if self._t < self._gaze_move_until:
            u = (self._t - self._gaze_move_start_t) / max(self._gaze_transition_len, 1e-6)
            u = max(0.0, min(1.0, u))
            s = u * u * (3.0 - 2.0 * u)
            self._gx = self._gx0 + (self._gx_tar - self._gx0) * s
            self._gy = self._gy0 + (self._gy_tar - self._gy0) * s
            self._gc = self._gc0 + (self._gc_tar - self._gc0) * s
        elif self._t < self._gaze_dwell_until:
            self._gx, self._gy = self._gx_tar, self._gy_tar
            self._gc = self._gc_tar
        else:
            self._gx, self._gy = self._gx_tar, self._gy_tar
            self._gc = self._gc_tar
            self._pick_new_gaze_target()
