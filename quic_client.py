import asyncio
import argparse
import logging
import pickle
import ssl
from typing import Optional, cast

from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, DatagramFrameReceived, StreamDataReceived
from aioquic.tls import SessionTicket

from quic_logger import QuicDirectoryLogger

from protocol.client import connect
from protocol.socketFactory import QuicFactorySocket

logger = logging.getLogger("client")


class QuicClient(QuicFactorySocket):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ack_waiter: Optional[asyncio.Future[None]] = None

    async def quic_datagram_send(self) -> None:
        self._quic.send_datagram_frame(b'quic')

        waiter = self._loop.create_future()
        self._ack_waiter = waiter
        self.transmit()

        return await asyncio.shield(waiter)

    async def quic_stream_send(self) -> None:
        stream_id = self._quic.get_next_available_stream_id()
        logger.debug(f"Stream ID: {stream_id}")
        if stream_id == 8:
            self.reset_stream(stream_id, 0)
            stream_id = self._quic.get_next_available_stream_id()
        data = b'quic stream-data send'
        end_stream = False
        self._quic.send_stream_data(stream_id, data, end_stream)

        waiter = self._loop.create_future()
        self._ack_waiter = waiter
        self.transmit()

        return await asyncio.shield(waiter)

    def quic_event_received(self, event: QuicEvent) -> None:
        if self._ack_waiter is not None:
            if isinstance(event, DatagramFrameReceived) and event.data == b'quic-ack':
                waiter = self._ack_waiter
                self._ack_waiter = None
                waiter.set_result(None)

            elif isinstance(event, StreamDataReceived):
                logger.info(event.data)
                waiter = self._ack_waiter
                self._ack_waiter = None
                waiter.set_result(None)


async def run(configuration: QuicConfiguration, host: str, port: int, zero_rtt: bool) -> None:
    async with connect(
        host, port,
        configuration=configuration,
        create_protocol=QuicClient,
        wait_connected=not zero_rtt,
    ) as client:
        client = cast(QuicClient, client)
        logger.info("sending quic ack")
        await client.quic_datagram_send()
        logger.info("recieved quic ack")
        logger.info("sending quic data in stream")
        for i in range(5):
            await client.quic_stream_send()
        logger.info("recieved quic data in stream")


def save_session_ticket(ticket: SessionTicket) -> None:
    """
    Callback which is invoked by the TLS engine when a new session ticket
    is received.
    """
    logger.info("New session ticket received")
    if args.session_ticket:
        with open(args.session_ticket, "wb") as fp:
            pickle.dump(ticket, fp)


if __name__ == "__main__":
    defaults = QuicConfiguration(is_client=True)
    print(defaults)
    parser = argparse.ArgumentParser(description="QUIC client")
    parser.add_argument(
        "host", type=str, help="The remote peer's host name or IP address"
    )
    parser.add_argument("port", type=int, help="The remote peer's port number")
    parser.add_argument(
        "--ca-certs", type=str,
        help="load CA certificates from the specified file"
    )
    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        help="do not validate server certificate",
    )
    parser.add_argument(
        "-i",
        "--include",
        action="store_true",
        help="include the HTTP response headers in the output",
    )
    parser.add_argument(
        "--output-dir", type=str,
        help="write downloaded files to this directory",
    )
    parser.add_argument(
        "-q",
        "--quic-log",
        type=str,
        help="log QUIC events to QLOG files in the specified directory",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="increase logging verbosity"
    )
    parser.add_argument(
        "-l",
        "--secrets-log",
        type=str,
        help="log secrets to a file, for use with Wireshark",
    )
    parser.add_argument(
        "--zero-rtt", action="store_true",
        help="try to send requests using 0-RTT"
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    configuration = QuicConfiguration(
        alpn_protocols=['quic'], is_client=True, max_datagram_frame_size=65536
    )

    if args.ca_certs:
        configuration.load_verify_locations(args.ca_certs)
    if args.insecure:
        configuration.verify_mode = ssl.CERT_NONE
    if args.quic_log:
        configuration.quic_logger = QuicDirectoryLogger(args.quic_log)
    if args.secrets_log:
        configuration.secrets_log_file = open(args.secrets_log, "a")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        run(
            configuration=configuration,
            host=args.host,
            port=args.port,
            zero_rtt=args.zero_rtt,
        )
    )
