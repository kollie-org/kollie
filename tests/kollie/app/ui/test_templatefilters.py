from datetime import datetime

import pytest
from freezegun import freeze_time

from kollie.app.ui.templatefilters import humanise_date_filter


@freeze_time("2024-01-01 12:00:00")
@pytest.mark.parametrize(
    "input_dt, expected_age",
    [
        pytest.param(
            datetime(2024, 1, 1, 11, 59, 0), "a minute ago", id="a minute ago"
        ),
        pytest.param(
            datetime(2024, 1, 1, 11, 58, 0), "2 minutes ago", id="2 minutes ago"
        ),
        pytest.param(
            datetime(2024, 1, 1, 11, 30, 0), "30 minutes ago", id="30 minutes ago"
        ),
        pytest.param(datetime(2024, 1, 1, 10, 59, 0), "an hour ago", id="an hour ago"),
        pytest.param(datetime(2024, 1, 1, 0, 0, 0), "12 hours ago", id="12 hours ago"),
        pytest.param(datetime(2023, 12, 31, 12, 0, 0), "a day ago", id="a day ago"),
        pytest.param(datetime(2023, 12, 22, 12, 0, 0), "a week ago", id="10 day ago"),
    ],
)
def test_age_filter(input_dt: datetime, expected_age: str):
    assert humanise_date_filter(input_dt) == expected_age
