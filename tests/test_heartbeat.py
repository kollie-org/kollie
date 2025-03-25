from unittest.mock import patch, mock_open
from kollie import heartbeat


@patch("kollie.heartbeat.open", new_callable=mock_open)
@patch("time.time", return_value=12345)
@patch("time.sleep", side_effect=Exception("exit the loop"))
@patch("kollie.heartbeat.logger")
def test_update_alive_file(mock_logger, mock_sleep, mock_time, mock_open):
    try:
        heartbeat.update_alive_file()
    except Exception:
        # Raise the exception to exit the loop
        pass
    mock_open().write.assert_called_once_with("12345")
    mock_time.assert_called_once()
    mock_sleep.assert_called_once_with(60)
    mock_logger.info.assert_called_once_with("Updated /tmp/alive.txt")
    mock_logger.error.assert_called_once_with(
        "Failed to update /tmp/alive.txt: exit the loop"
    )


def test_start_heartbeat():
    with patch("threading.Thread") as MockThread:
        heartbeat.start_heartbeat()
    MockThread.assert_called_once_with(target=heartbeat.update_alive_file, daemon=True)
    MockThread().start.assert_called_once()
