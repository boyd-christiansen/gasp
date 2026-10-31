"""Eight-inch water-impact disk with a central spire and organic ripples."""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy.special import j0

from cadgen import build123d as bd
from cadgen import srgb, step, stl


INCH_MM = 25.4
DISK_DIAMETER_MM = 8.0 * INCH_MM
DISK_RADIUS_MM = DISK_DIAMETER_MM / 2.0
BACK_Z_MM = 0.0
NOMINAL_WATERLINE_MM = 8.5
EDGE_ROLLOFF_START_MM = 76.0
WAVE_FADE_START_MM = 88.0
EDGE_DROP_END_DERIVATIVE = 1.0

# Scaled physical event: a roughly 1.8 mm impact footprint in 30 mm-deep water,
# viewed 55 ms after impact and enlarged 3x to fill the eight-inch sculpture.
WATER_DENSITY_KG_M3 = 998.0
WATER_SURFACE_TENSION_N_M = 0.072
WATER_KINEMATIC_VISCOSITY_M2_S = 1.004e-6
PHYSICAL_WATER_DEPTH_M = 0.030
PHYSICAL_IMPACT_RADIUS_M = 0.0009
SNAPSHOT_TIME_S = 0.055
GEOMETRIC_SCALE = 3.0
SPECTRAL_WAVE_AMPLITUDE_MM = 3.0


def _gaussian_ring(
    radius_mm: float, center_mm: float, width_mm: float, height_mm: float
) -> float:
    """Smooth local crest or trough in the radial water profile."""
    return height_mm * math.exp(-(((radius_mm - center_mm) / width_mm) ** 2))


def _smootherstep(value: float) -> float:
    """Quintic C2 blend with zero slope and curvature at both ends."""
    value = max(0.0, min(1.0, value))
    return value**3 * (value * (value * 6.0 - 15.0) + 10.0)


def _terminal_drop(value: float) -> float:
    """C2-start taper that reaches the back with a continuing terminal slope."""
    value = max(0.0, min(1.0, value))
    derivative = EDGE_DROP_END_DERIVATIVE
    return (
        (10.0 - 4.0 * derivative) * value**3
        + (7.0 * derivative - 15.0) * value**4
        + (6.0 - 3.0 * derivative) * value**5
    )


@lru_cache(maxsize=1)
def _capillary_spectrum() -> tuple[np.ndarray, np.ndarray, float, float]:
    """Return a damped axisymmetric capillary-gravity impulse spectrum."""
    wave_numbers = np.linspace(25.0, 4000.0, 1600)
    angular_frequency = np.sqrt(
        (
            9.81 * wave_numbers
            + WATER_SURFACE_TENSION_N_M
            / WATER_DENSITY_KG_M3
            * wave_numbers**3
        )
        * np.tanh(wave_numbers * PHYSICAL_WATER_DEPTH_M)
    )
    weights = (
        np.exp(-0.5 * (wave_numbers * PHYSICAL_IMPACT_RADIUS_M) ** 2)
        * wave_numbers
        * np.exp(
            -2.0
            * WATER_KINEMATIC_VISCOSITY_M2_S
            * wave_numbers**2
            * SNAPSHOT_TIME_S
        )
        * np.cos(angular_frequency * SNAPSHOT_TIME_S)
    )
    physical_edge_radius_m = DISK_RADIUS_MM / (1000.0 * GEOMETRIC_SCALE)
    edge_value = float(
        np.trapezoid(weights * j0(wave_numbers * physical_edge_radius_m), wave_numbers)
    )
    sample_radii_m = np.linspace(0.006, physical_edge_radius_m, 240)
    sample_values = np.array(
        [
            np.trapezoid(weights * j0(wave_numbers * radius_m), wave_numbers)
            - edge_value
            for radius_m in sample_radii_m
        ]
    )
    normalization = float(np.max(np.abs(sample_values)))
    return wave_numbers, weights, edge_value, normalization


def _capillary_wave_mm(radius_mm: float) -> float:
    """Axisymmetric Hankel-mode reconstruction of the transient wave train."""
    wave_numbers, weights, edge_value, normalization = _capillary_spectrum()
    physical_radius_m = radius_mm / (1000.0 * GEOMETRIC_SCALE)
    displacement = float(
        np.trapezoid(weights * j0(wave_numbers * physical_radius_m), wave_numbers)
    )
    return SPECTRAL_WAVE_AMPLITUDE_MM * (
        displacement - edge_value
    ) / normalization

def water_height_mm(radius_mm: float) -> float:
    """Early rebound profile combining nonlinear jetting and linear wave physics."""
    # The cavity-collapse jet is nonlinear, so it is represented separately from
    # the small-amplitude wave field by a rounded, focused central profile.
    spindle = _gaussian_ring(radius_mm, 0.0, 1.7, 12.0) + _gaussian_ring(
        radius_mm, 0.0, 4.0, 3.5
    )
    collapsing_cavity = _gaussian_ring(radius_mm, 7.5, 3.5, -5.0)
    rebound_collar = _gaussian_ring(radius_mm, 15.5, 4.2, 3.8)

    # The outgoing rings come from the capillary-gravity dispersion relation,
    # reconstructed as radial J0 modes. This creates naturally changing spacing
    # and viscous amplitude loss rather than a repeated decorative waveform.
    wave_gate = _smootherstep((radius_mm - 11.0) / 11.0)
    wave_fade = 1.0 - _smootherstep(
        (radius_mm - WAVE_FADE_START_MM)
        / (DISK_RADIUS_MM - WAVE_FADE_START_MM)
    )
    capillary_waves = _capillary_wave_mm(radius_mm) * wave_gate * wave_fade

    # Continue the support taper directly into the flat back. Unlike a symmetric
    # smoothstep, this blend retains a downward terminal slope and creates no lip.
    edge_envelope = 1.0 - _terminal_drop(
        (radius_mm - EDGE_ROLLOFF_START_MM)
        / (DISK_RADIUS_MM - EDGE_ROLLOFF_START_MM)
    )
    base_height = edge_envelope * NOMINAL_WATERLINE_MM
    return (
        base_height
        + spindle
        + collapsing_cavity
        + rebound_collar
        + capillary_waves
    )


def _profile_radii() -> list[float]:
    # Closely sample the jet; 2 mm spacing is ample for the broad outer waves
    # while keeping the exact revolved surface compact and portable.
    return [
        0.0,
        0.25,
        0.5,
        0.8,
        1.1,
        1.5,
        2.0,
        2.7,
        3.5,
        4.5,
        5.5,
        6.5,
        7.5,
    ] + [float(radius_mm) for radius_mm in range(8, 102, 2)] + [DISK_RADIUS_MM]


def _revolved_water_disk() -> bd.Shape:
    radii = _profile_radii()
    top_points = [(radius_mm, 0.0, water_height_mm(radius_mm)) for radius_mm in radii]
    terminal_slope = -(
        NOMINAL_WATERLINE_MM
        * EDGE_DROP_END_DERIVATIVE
        / (DISK_RADIUS_MM - EDGE_ROLLOFF_START_MM)
    )
    top_curve = bd.Edge.make_spline(
        top_points,
        tangents=[(1.0, 0.0, 0.0), (1.0, 0.0, terminal_slope)],
        scale=False,
    )
    center_bottom = (0.0, 0.0, BACK_Z_MM)
    profile = bd.Wire(
        edges=[
            top_curve,
            bd.Edge.make_line(top_points[-1], center_bottom),
            bd.Edge.make_line(center_bottom, top_points[0]),
        ],
        sequenced=True,
    )
    return bd.Solid.revolve(bd.Face(profile), 360.0, bd.Axis.Z)


def make_ripple_panel() -> bd.Shape:
    """Return the preserved, unperforated base geometry."""
    return _revolved_water_disk()


@step(
    out="../STEP/ripple_panel.step",
    materials={
        "definitions": {
            "deep_water": {
                "name": "Deep blue gloss",
                "baseColor": "#2F6F9F",
                "roughness": 0.2,
                "metalness": 0.05,
                "clearcoat": 0.75,
                "clearcoatRoughness": 0.12,
            }
        },
        "assignments": [{"targets": ["#ripple_panel"], "material": "deep_water"}],
    },
)
@stl(
    out="../STL/ripple_panel.stl",
    mesh_tolerance=1.5e-3,
    mesh_angular_tolerance=0.18,
)
def ripple_panel():
    body = make_ripple_panel()
    body.label = "ripple_panel"
    body.color = srgb("#2F6F9F")
    return body


if __name__ == "__main__":
    ripple_panel()
