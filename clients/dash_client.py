import asyncio
import logging
import json
import time
import os
from glob import glob
from pprint import pformat

from collections import namedtuple
from queue import Queue

from aioquic.quic.configuration import QuicConfiguration
from protocol.h3.socketFactory import QuicFactorySocket
from clients.h3_client import perform_http_request, process_http_pushes

from adaptive.abr import BasicABR
from adaptive.mpc import MPC
from adaptive.bola import Bola
from adaptive.BBA0 import BBA0
from adaptive.BBA2 import BBA2

import config

logger = logging.getLogger("DASH client")

adaptiveInfo = namedtuple("AdaptiveInfo",
                          'segment_time bitrates segments')
downloadInfo = namedtuple("DownloadInfo",
                          'index file_name url quality resolution size downloaded time')
NetworkPeriod = namedtuple('NetworkPeriod', 'time bandwidth latency')


def segment_download_info(manifest, fname, size, idx, url, quality, resolution, time):
    if size <= 0:
        return downloadInfo(index=idx, file_name=None, url=None, quality=quality, resolution=resolution, size=0, downloaded=0, time=0)
    else:
        return downloadInfo(index=idx, file_name=fname, url=url, quality=quality, resolution=resolution, size=size, downloaded=size, time=time)


def select_abr_algorithm(manifest_data, args):
	if args.abr == "BBA0":
		return BBA0(manifest_data)
	elif args.abr == 'Bola':
		return Bola(manifest_data)
	elif args.abr == 'tputRule':
		return BasicABR(manifest_data)
	elif args.abr == 'MPC':
		return MPC(manifest_data)
	elif args.abr == 'BBA2':
		return BBA2(manifest_data)
	else:
		logger.error("Error!! No right rule specified")
		return


class DashClient:
	def __init__(self, protocol: QuicFactorySocket, args):
		self.protocol = protocol
		self.args = args
		self.manifest_data = None
		self.latest_tput = 0

		self.lock = asyncio.Lock()
		self.totalBuffer = args.buffer_size
		self.currBuffer = 0
		self.abr_algorithm = None
		self.segment_baseName = None

		self.lastDownloadSize = 0
		self.lastDownloadTime = 0
		self.segmentQueue = asyncio.Queue()
		self.frameQueue = asyncio.Queue()

		self.perf_parameters = {}
		self.perf_parameters['startup_delay'] = 0
		self.perf_parameters['total_time_elapsed'] = 0
		self.perf_parameters['bitrate_change'] = []
		self.perf_parameters['prev_rate'] = 0
		self.perf_parameters['change_count'] = 0
		self.perf_parameters['rebuffer_time'] = 0.0
		self.perf_parameters['avg_bitrate'] = 0.0
		self.perf_parameters['avg_bitrate_change'] = 0.0
		self.perf_parameters['rebuffer_count'] = 0
		self.perf_parameters['tput_observed'] = []

	async def download_manifest(self) -> None:
		#TODO: Cleanup: globally intakes a list of urls, while here
		# we only consider a single urls per event.
		logger.info("Downloading Manifest file")
		# Include is hard-coded to be False as JSON parser would fail to
		# parse any parameters which aren't valid JSON format.
		process_http_pushes(client=self.protocol, include=self.args.include, output_dir=self.args.output_dir)
		res = await perform_http_request(client=self.protocol,
										url=self.args.urls[0],
										data=self.args.data,
										include=False,
										output_dir=self.args.output_dir)

		self.baseUrl, self.filename = os.path.split(self.args.urls[0])
		self.manifest_data = json.load(open(config.ROOT_PATH + ".cache/" + self.filename))
		self.lastDownloadSize = res[0]
		self.latest_tput = res[1]
		self.lastDownloadTime = res[2]

	async def dash_client_set_config(self) -> None:
		logger.info("DASH client initialization in process")
		await self.download_manifest()
		self.abr_algorithm = select_abr_algorithm(self.manifest_data, self.args)
		self.currentSegment = self.manifest_data['start_number']
		self.totalSegments = self.getTotalSegments()

	def getTotalSegments(self):
		return self.manifest_data['total_segments']

	def getDuration(self):
		return self.manifest_data['total_duration']

	def getCorrespondingBitrateIndex(self, bitrate):
		for i, b in enumerate(self.manifest_data['bitrates_kbps']):
			if b == bitrate:
				return i + 1
		return -1

	def latest_segment_Throughput_kbps(self):
		# returns throughput value of last segment downloaded in kbps
		return self.latest_tput
	
	async def fetchNextSegment(self, segment_list, bitrate = 0):
		if not bitrate:
			return

		segment_Duration = 0

		for i, b in enumerate(self.manifest_data['bitrates_kbps']):
			if b == bitrate:
				segment_Duration = int(self.manifest_data['segment_duration_ms']) / int(self.manifest_data['timescale'])
				break

		for fname in sorted(glob(segment_list)):
			_, self.segment_baseName = fname.rsplit('/', 1)
			self.args.urls[0] = self.baseUrl.rstrip('manifest') + str(os.stat(fname).st_size)
			start = time.time()

			res = await perform_http_request(client=self.protocol,
											url=self.args.urls[0],
											data=self.args.data,
											include=self.args.include,
											output_dir=self.args.output_dir)

			elapsed = time.time() - start

		data = res[0]
		if data is not None:
			self.lastDownloadTime = elapsed
			self.lastDownloadSize = data
			self.latest_tput =  res[1]

			await self.segmentQueue.put(self.segment_baseName)

			# QOE parameters update
			self.perf_parameters['bitrate_change'].append((self.currentSegment + 1,  bitrate))
			self.perf_parameters['tput_observed'].append((self.currentSegment + 1,  res[1]))
			self.perf_parameters['avg_bitrate'] += bitrate
			self.perf_parameters['avg_bitrate_change'] += abs(bitrate - self.perf_parameters['prev_rate'])

			if not self.perf_parameters['prev_rate'] or self.perf_parameters['prev_rate'] != bitrate:
				self.perf_parameters['prev_rate'] = bitrate
				self.perf_parameters['change_count'] += 1

			self.currentSegment += 1
			async with self.lock:
					self.currBuffer += segment_Duration

			ret = True
		else:
			logger.fatal("Error: downloaded segment is none!! Playback will stop shortly")
			ret = False
		return ret

	async def download_segment(self) -> None:
		if config.NUM_SERVER_PUSHED_FRAMES is not None:
			self.currentSegment = config.NUM_SERVER_PUSHED_FRAMES + 1
			for i in range(1, config.NUM_SERVER_PUSHED_FRAMES + 1):
				await self.segmentQueue.put("Frame-pushed-" + str(i) + ".ppm")
		else:
			self.currentSegment += 1

		while self.currentSegment <= 4:
			async with self.lock:
				currBuff = self.currBuffer

			segment_Duration = int(self.manifest_data['segment_duration_ms']) / int(self.manifest_data['timescale'])

			playback_stats = {}
			playback_stats["lastTput_kbps"] = self.latest_segment_Throughput_kbps()
			playback_stats["currBuffer"] = currBuff
			playback_stats["segment_Idx"] = self.currentSegment + 1

			logger.info(pformat(playback_stats))

			if self.totalBuffer - currBuff >= segment_Duration:
				rateNext = self.abr_algorithm.NextSegmentQualityIndex(playback_stats)
				segment_resolution = self.manifest_data['resolutions'][rateNext]
				fName = "htdocs/dash/" + segment_resolution + "/out/frame-" + str(self.currentSegment) + "-" + segment_resolution + "-*"
				if await self.fetchNextSegment(fName, rateNext):
					dp = segment_download_info(self.manifest_data, self.segment_baseName, self.lastDownloadSize, self.currentSegment, self.args.urls, rateNext, segment_resolution, self.lastDownloadTime)
					logger.info(dp)
				else:
					break
			else:
				asyncio.sleep(1)

		await self.segmentQueue.put("Download complete")
		logger.info("All the segments have been downloaded")

	#emulate playback of frame scenario
	async def playback_frames(self) -> None:
		#Flag to mark whether placback has started or not.
		has_playback_started = False
		while True:
			await asyncio.sleep(1)
			rebuffer_start = time.time()
			frame = await self.frameQueue.get()
			rebuffer_elapsed = time.time() - rebuffer_start

			if frame == "Decoding complete":
				logger.info("All the segments have been played back")
				break

			if not has_playback_started:
				has_playback_started = True
				self.perf_parameters['startup_delay'] = time.time()
			else:
				self.perf_parameters['rebuffer_time'] += rebuffer_elapsed

			if rebuffer_elapsed > 0.0001:
				logger.info('rebuffer_time:{}'.format(rebuffer_elapsed))
				self.perf_parameters['rebuffer_count'] += 1
			async with self.lock:
				self.currBuffer -= 2
			logger.info("Played segments: {}".format(frame))

	#emulate decoding the frame scenario
	async def decode_frames(self) -> None:
		while True:
			await asyncio.sleep(1)
			segment = await self.segmentQueue.get()
			if segment == "Download complete":
				logger.info("All the segments have been decoded")
				await self.frameQueue.put("Decoding complete")
				break

			logger.info("Decoded segments: {}".format(segment))
			await self.frameQueue.put(segment)

	async def player(self) -> None:
		await self.dash_client_set_config()

		tasks = [asyncio.ensure_future(self.download_segment()),
				asyncio.ensure_future(self.decode_frames()),
				asyncio.ensure_future(self.playback_frames())]

		await asyncio.gather(*tasks)

		self.perf_parameters['avg_bitrate'] /= self.totalSegments
		self.perf_parameters['avg_bitrate_change'] /= (self.totalSegments - 1)
