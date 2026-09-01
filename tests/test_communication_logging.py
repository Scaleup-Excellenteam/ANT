import inspect
import logging

import pytest

from src.communication_logging import SatelliteCommunicationLogger


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def communication(clock):
    return SatelliteCommunicationLogger(
        clock=clock, high_latency_seconds=2.0, low_bandwidth_kbps=256.0
    )


def messages(caplog):
    return [record.getMessage() for record in caplog.records]


def test_message_id_and_priority_are_logged(communication, caplog):
    with caplog.at_level(logging.DEBUG):
        communication.message_sent(421, priority="high")
        communication.waiting_for_ack(421)
    assert any("Sending message id=421 priority=high" in item for item in messages(caplog))
    assert any("Waiting for ACK id=421" in item for item in messages(caplog))


def test_latency_is_measured_from_send_to_ack(communication, clock, caplog):
    with caplog.at_level(logging.DEBUG):
        communication.message_sent(421)
        clock.advance(1.8)
        latency = communication.ack_received(421)
    assert latency == pytest.approx(1.8)
    assert any("ACK received id=421 latency=1.800s" in item for item in messages(caplog))
    assert any(record.name == "satellite.latency" for record in caplog.records)


def test_ack_timeout_uses_warning(communication, caplog):
    with caplog.at_level(logging.WARNING):
        communication.ack_timeout(421)
    assert caplog.records[-1].levelno == logging.WARNING
    assert "ACK timeout id=421" in caplog.records[-1].getMessage()


def test_retry_and_limit_exhausted_use_expected_levels(communication, caplog):
    with caplog.at_level(logging.DEBUG):
        communication.retry(421, attempt=1, max_attempts=3)
        communication.retry_limit_exhausted(421, attempts=3)
    assert [(record.name, record.levelno) for record in caplog.records] == [
        ("satellite.retry", logging.WARNING),
        ("satellite.retry", logging.ERROR),
    ]


def test_connection_lost_and_restored_include_downtime(communication, clock, caplog):
    with caplog.at_level(logging.DEBUG):
        communication.connection_lost()
        clock.advance(81.2)
        downtime = communication.connection_restored()
    assert downtime == pytest.approx(81.2)
    assert any(record.levelno == logging.WARNING and "Connection lost" in record.getMessage()
               for record in caplog.records)
    assert any("Connection restored downtime=81.200s" in item for item in messages(caplog))


def test_queue_size_and_resend_are_logged(communication, caplog):
    with caplog.at_level(logging.DEBUG):
        communication.message_queued(421, queue_size=14)
        communication.resend_queued_message(421, queue_size=13)
    assert any("Message queued id=421 queue_size=14" in item for item in messages(caplog))
    assert any("Resending queued message id=421 queue_size=13" in item
               for item in messages(caplog))


def test_low_bandwidth_warning_only_occurs_on_state_transition(communication, caplog):
    with caplog.at_level(logging.DEBUG):
        communication.bandwidth_measured(120)
        communication.bandwidth_measured(100)
        communication.bandwidth_measured(512)
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "bandwidth_kbps=120.0" in warnings[0].getMessage()
    assert any("Low-bandwidth mode activated" in item for item in messages(caplog))
    assert any("Low-bandwidth mode deactivated" in item for item in messages(caplog))


def test_payload_byte_counts_and_ratio_are_logged(communication, caplog):
    with caplog.at_level(logging.DEBUG):
        communication.payload_size(81920, 22528)
    output = messages(caplog)[-1]
    assert "original_bytes=81920" in output
    assert "transmitted_bytes=22528" in output
    assert "compression_ratio=0.275" in output


def test_high_latency_uses_warning(communication, caplog):
    with caplog.at_level(logging.DEBUG):
        communication.ack_received(421, latency_seconds=3.5)
    assert any(record.levelno == logging.WARNING and "High latency" in record.getMessage()
               for record in caplog.records)


def test_delivery_and_permanent_failure_are_logged(communication, caplog):
    with caplog.at_level(logging.DEBUG):
        communication.message_delivered(421)
        communication.message_failed(422, failure_code="link_unavailable")
    assert any("Message delivered id=421" in item for item in messages(caplog))
    assert any(record.levelno == logging.ERROR and "failure_code=link_unavailable"
               in record.getMessage() for record in caplog.records)


def test_public_api_cannot_accept_payloads_or_secrets(communication, caplog):
    assert "payload" not in inspect.signature(communication.message_sent).parameters
    assert "token" not in inspect.signature(communication.message_sent).parameters
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(TypeError):
            communication.message_sent(421, payload="TOP_SECRET_CONTENT")
    assert "TOP_SECRET_CONTENT" not in caplog.text


def test_unexpected_exception_logs_traceback_with_sensitive_details_redacted(
    communication, caplog
):
    with caplog.at_level(logging.ERROR):
        try:
            raise RuntimeError("transport failed with SECRET_TOKEN")
        except RuntimeError:
            communication.unexpected_exception("send", 421)
    record = caplog.records[-1]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert "operation=send id=421" in record.getMessage()
    assert "SECRET_TOKEN" not in caplog.text
    assert "exception details redacted" in caplog.text
