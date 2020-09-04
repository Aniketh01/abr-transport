import asyncio
import json
import ssl
import time
import os
import argparse
import pickle
import logging
from typing import Deque, Dict, List, Optional, Union, cast
from urllib.parse import urlparse

from pprint import pformat

try:
    import uvloop
except ImportError:
    uvloop = None


from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.quic.configuration import QuicConfiguration

from aioquic.tls import SessionTicket

from clients.dash_client import DashClient
from protocol.client import connect
from clients.quic_client import QuicClient
from clients.h3_client import HttpClient

from quic_logger import QuicDirectoryLogger

import config
from adaptive.mpc import MPC

logger = logging.getLogger("DASH Player")


def save_session_ticket(ticket: SessionTicket) -> None:
    """
    Callback which is invoked by the TLS engine when a new session ticket
    is received.
    """
    logger.info("New session ticket received")
    if args.session_ticket:
        with open(args.session_ticket, "wb") as fp:
            pickle.dump(ticket, fp)


async def run(configuration: QuicConfiguration, args) -> None:
    parsed = urlparse(args.urls[0])
    assert parsed.scheme in (
        "https",
        "quic",
    ), "Only https:// or quic:// URLs are supported."
    if ":" in parsed.netloc:
        host, port_str = parsed.netloc.split(":")
        port = int(port_str)
    else:
        host = parsed.netloc
        port = 443

    if args.session_ticket is not None:
        session_ticket = save_session_ticket
    else:
        session_ticket = None

    if args.legacy_quic is True:
        async with connect(
            host, port,
            configuration=configuration,
            create_protocol=QuicClient,
            wait_connected=not args.zero_rtt,
        ) as client:
            client = cast(QuicClient, client)
            logger.info("sending quic ack")
            await client.quic_datagram_send()
            logger.info("recieved quic ack")
            logger.info("sending quic data in stream")
            for i in range(5):
                await client.quic_stream_send()
            logger.info("recieved quic data in stream")
    else:
        async with connect(
            host,
            port,
            configuration=configuration,
            create_protocol=HttpClient,
            session_ticket_handler=session_ticket,
            local_port=args.local_port,
            wait_connected=not args.zero_rtt,
        ) as client:
            h3_client = cast(HttpClient, client)

            dc = DashClient(protocol=h3_client, args=args)

            start = time.time()
            await dc.player()
            elapsed = time.time() - start

            dc.perf_parameters['total_time_played'] = elapsed
            dc.perf_parameters['startup_delay'] = dc.perf_parameters['startup_delay'] - start

            dc.perf_parameters['MPC_QOE'] = dc.perf_parameters['avg_bitrate'] - (config.LAMBDA * dc.perf_parameters['avg_bitrate_change']) \
                                            - (config.MU * dc.perf_parameters['rebuffer_time']) - (config.MU * dc.perf_parameters['startup_delay'])

            logger.info("Playback completed")
            logger.info(pformat(dc.perf_parameters))


if __name__ == "__main__":
    defaults = QuicConfiguration(is_client=True)
    parser = argparse.ArgumentParser(description="The player, A streaming client supporting multiple ABR options and both QUIC and HTTP/3 support")
    parser.add_argument(
        "--urls", type=str, nargs="+", help="the URL to query (must be HTTPS)"
    )
    parser.add_argument(
        "--manifest-file", type=str, help="Path to the custom manifest file"
    )
    parser.add_argument("--legacy-quic", action="store_true", help="use QUIC")
    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        help="do not validate server certificate",
    )
    parser.add_argument(
        "-d", "--data", type=str, help="send the specified data in a POST request"
    )
    parser.add_argument(
        "--ca-certs", type=str, help="load CA certificates from the specified file"
    )
    parser.add_argument(
        "--output-dir", type=str, help="write downloaded files to this directory",
    )
    parser.add_argument(
        "--local-port", type=int, default=0, help="local port to bind for connections",
    )
    parser.add_argument(
        "-s",
        "--session-ticket",
        type=str,
        help="read and write session ticket from the specified file",
    )
    parser.add_argument(
        "-q",
        "--quic-log",
        type=str,
        help="log QUIC events to QLOG files in the specified directory",
    )
    parser.add_argument(
        "--zero-rtt", action="store_true", help="try to send requests using 0-RTT"
    )
    parser.add_argument(
        "--max-data",
        type=int,
        help="connection-wide flow control limit (default: %d)" % defaults.max_data,
    )
    parser.add_argument(
        "--max-stream-data",
        type=int,
        help="per-stream flow control limit (default: %d)" % defaults.max_stream_data,
    )
    parser.add_argument(
        "-l",
        "--secrets-log",
        type=str,
        help="log secrets to a file, for use with Wireshark",
    )
    parser.add_argument(
        "-i",
        "--include",
        action="store_true",
        help="include the HTTP response headers in the output",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )

    # Start of ABR/streaming related config parameters
    parser.add_argument("-b", "--buffer-size", action="store",
						default=60, help="Buffer size for video playback")
    parser.add_argument("--abr", "--abr", action="store", 
						default="tputRule", help="ABR rule to download video")

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    if args.urls is None:
        logger.info("URL to download is provided by the dash client directly")

    if args.output_dir is not None and not os.path.isdir(args.output_dir):
        raise Exception("%s is not a directory" % args.output_dir)
    elif args.output_dir is None:
        args.output_dir = config.OUT_DIR

    if args.manifest_file is None:
        args.manifest_file = config.MANIFEST_FILE
    manifest = json.load(open(args.manifest_file))

    configuration = QuicConfiguration(
        is_client=True,
        alpn_protocols=['quic'] if args.legacy_quic else H3_ALPN,
        max_datagram_frame_size=65536
    )

    if args.ca_certs is None:
        args.ca_certs = config.CA_CERTS
    configuration.load_verify_locations(args.ca_certs)

    if args.quic_log:
        configuration.quic_logger = QuicDirectoryLogger(args.quic_log)
    if args.insecure:
        configuration.verify_mode = ssl.CERT_NONE
    if args.max_data:
        configuration.max_data = args.max_data
    if args.max_stream_data:
        configuration.max_stream_data = args.max_stream_data
    if args.secrets_log:
        configuration.secrets_log_file = open(args.secrets_log, "a")
    if args.session_ticket:
        try:
            with open(args.session_ticket, "rb") as fp:
                configuration.session_ticket = pickle.load(fp)
        except FileNotFoundError:
            pass

    if uvloop is not None:
        uvloop.install()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        run(configuration=configuration, args=args)
    )

    # a = mpc.MPC(manifest)
    # # for i in range(0, 100, 10):
    # #     q = a.NextSegmentQualityIndex(10, i)
    # #     print("bitrate: {} buffer: {}".format(q, i))
    # q = a.NextSegmentQualityIndex(10)
    # print(q)