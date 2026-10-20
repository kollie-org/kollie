from unittest.mock import patch

import pytest

from kollie.cluster.authentication import connect_to_cluster
from kollie.constants import LOCAL_STAGE, PROD_STAGE, TEST_STAGE


@pytest.mark.parametrize(
    "stage, expected_call",
    [
        (LOCAL_STAGE, "kollie.cluster.authentication._connect_using_local_kubeconfig"),
        (PROD_STAGE, "kollie.cluster.authentication._connect_in_cluster_mode"),
    ],
)
def test_connect_to_cluster(stage, expected_call):
    with patch("os.environ.get", return_value=stage), patch(
        expected_call
    ) as mock_connect:
        connect_to_cluster()
        mock_connect.assert_called_once()


def test_connect_to_cluster_test_stage():
    with patch("os.environ.get", return_value=TEST_STAGE), pytest.raises(
        RuntimeError
    ):
        connect_to_cluster()


def test_connect_to_cluster_exception():
    with patch("os.environ.get", return_value=PROD_STAGE), patch(
        "kollie.cluster.authentication._connect_in_cluster_mode", side_effect=TypeError
    ), pytest.raises(TypeError):
        connect_to_cluster()
