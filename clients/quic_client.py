import asyncio
import argparse
import logging
import pickle
import ssl
from typing import Optional, cast, List
from urllib.parse import urlparse

from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, DatagramFrameReceived, StreamDataReceived

from protocol.client import connect
from protocol.socketFactory import QuicFactorySocket

logger = logging.getLogger("quic client")


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
