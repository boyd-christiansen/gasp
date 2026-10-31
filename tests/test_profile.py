import pytest
from gasp.profile import bundled_profile, parse_profile


def test_profiles_fit_transport():
    p=bundled_profile();assert p.range_bins==64 and p.rx_count==4 and p.tx_count==3
    assert p.range_step_m==pytest.approx(.0585532)
    assert .6<p.summary()['uart_utilization']<.8
    assert bundled_profile('usb-phase-10hz').frame_hz==10
    assert bundled_profile('dca-raw').lvds_adc


def test_transport_profiles_share_the_verified_rf_schedule():
    profiles = [bundled_profile(name) for name in ('usb-phase-10hz', 'usb-phase-20hz', 'dca-raw')]
    for p in profiles:
        # The former 47 us schedule was accepted by the CLI but failed at sensorStart.
        # Keep USB and raw-ADC timing metadata consistent with the board-tested schedule.
        assert p.chirp_period_us == 83
        assert p.summary()['burst_duration_ms'] == pytest.approx(3.984)
    assert len({p.range_step_m for p in profiles}) == 1


@pytest.mark.parametrize('old,new',[
    ('clutterRemoval -1 0','clutterRemoval -1 1'),
    ('profileCfg 0 60.25','profileCfg 0 63.5'),
    ('64 2000','64 1000'),
    ('frameCfg 0 2 16 0 50','frameCfg 0 2 16 5 50'),
    ('chirpCfg 2 2 0 0 0 0 0 4','chirpCfg 2 2 0 0 0 0 0 1'),
])
def test_reject_invalid_rf_or_unsupported_layout(old,new):
    with pytest.raises(ValueError):parse_profile(bundled_profile().text.replace(old,new))
