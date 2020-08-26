import asyncio
import json
import time
import os
from glob import glob
from pprint import pprint

from collections import namedtuple
from queue import Queue

from aioquic.quic.configuration import QuicConfiguration

from adaptive.abr import BasicABR
from adaptive.mpc import MPC
from adaptive.bola import Bola
from adaptive.BBA0 import BBA0
from adaptive.BBA2 import BBA2

from clients.build import run

import config

adaptiveInfo = namedtuple("AdaptiveInfo",
                          'segment_time bitrates segments')
downloadInfo = namedtuple("DownloadInfo",
                          'index file_name url quality resolution size downloaded time')


def segment_download_info(manifest, fname, size, idx, url, quality, resolution, time):
    if size <= 0:
        return downloadInfo(index=idx, file_name=None, url=None, quality=quality, resolution=resolution, size=0, downloaded=0, time=0)
    else:
        return downloadInfo(index=idx, file_name=fname, url=url, quality=quality, resolution=resolution, size=size, downloaded=size, time=time)


async def perform_download(configuration: QuicConfiguration, args) -> None:
	if args.urls is None:
		args.urls = config.URLS

	res = await run(
            configuration=configuration,
            urls=args.urls,
            data=args.data,
            include=args.include,
            legacy_quic=args.legacy_quic,
            output_dir=args.output_dir,
            local_port=args.local_port,
            zero_rtt=args.zero_rtt,
            session_ticket=args.session_ticket,
        )
	return res

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
		print("Error!! No right rule specified")
		return


class DashClient:
	def __init__(self, configuration: QuicConfiguration, args):
		self.configuration = configuration
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
		self.segmentQueue = Queue(maxsize=0)
		self.frameQueue = Queue(maxsize=0)

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
		res = await perform_download(self.configuration, self.args)
		self.baseUrl, self.filename = os.path.split(self.args.urls[0])
		self.manifest_data = json.load(open(".cache/" + self.filename))
		self.lastDownloadSize = res[0][0]
		self.latest_tput = res[0][1]
		self.lastDownloadTime = res[0][2]

	async def dash_client_set_config(self) -> None:
		await self.download_manifest()
		self.abr_algorithm = select_abr_algorithm(self.manifest_data, self.args)
		self.currentSegment = self.manifest_data['start_number'] - 1
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
				segment_Duration = self.manifest_data['segment_duration_ms'] / self.manifest_data['timescale']
				break

		for fname in sorted(glob(segment_list)):
			_, self.segment_baseName = fname.rsplit('/', 1)
			self.args.urls[0] = self.baseUrl + '/' + str(os.stat(fname).st_size)
			start = time.time()
			res = await perform_download(self.configuration, self.args)
			elapsed = time.time() - start

		data = res[0][0]
		if data is not None:
			self.lastDownloadTime = elapsed
			self.lastDownloadSize = data
			self.latest_tput =  res[0][1]

			self.segmentQueue.put(self.segment_baseName)

			# QOE parameters update
			self.perf_parameters['bitrate_change'].append((self.currentSegment + 1,  bitrate))
			self.perf_parameters['tput_observed'].append((self.currentSegment + 1,  res[0][1]))
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
			print("Error: downloaded segment is none!! Playback will stop shortly")
			ret = False
		return ret

	async def download_segment(self) -> None:
		if config.NUM_SERVER_PUSHED_FRAMES is not None:
			next_segment_idx = config.NUM_SERVER_PUSHED_FRAMES + 1
		else:
			next_segment_idx = 1

		while self.currentSegment + 1 < self.totalSegments:
			async with self.lock:
				currBuff = self.currBuffer
			segment_Duration = int(self.manifest_data['segment_duration_ms']) / int(self.manifest_data['timescale'])

			playback_stats = {}
			playback_stats["lastTput_kbps"] = self.latest_segment_Throughput_kbps()
			playback_stats["currBuffer"] = currBuff
			playback_stats["segment_Idx"] = self.currentSegment + 1

			if self.totalBuffer - currBuff >= segment_Duration:
				rateNext = self.abr_algorithm.NextSegmentQualityIndex(playback_stats)
				while next_segment_idx <= len(self.manifest_data['segment_size_bytes']):
					segment_resolution = self.manifest_data['resolutions'][rateNext]
					fName = "htdocs/dash/" + segment_resolution + "/out/frame-" + str(next_segment_idx) + "-" + segment_resolution + "-*"
					if await self.fetchNextSegment(fName, rateNext):
						dp = segment_download_info(self.manifest_data, self.segment_baseName, self.lastDownloadSize, next_segment_idx, self.args.urls, rateNext, segment_resolution, self.lastDownloadTime)
						pprint(dp)
					else:
						break
					next_segment_idx += 1
			else:
				time.sleep(0.5)
		self.segmentQueue.put("done")


	#emulate playback of frame scenario
	async def playback_frames(self) -> None:
		print("playback seg")

	#emulate decoding the frame scenario
	async def decode_frames(self) -> None:
		print("decoding seg")

	async def player(self) -> None:
		await self.dash_client_set_config()

		#TODO: Design choice: should player handle downloading the manifest?
		#TODO: download the segments
		#TODO: decode the segements
		#TODO: play back the segments


		tasks = [self.download_segment(), self.decode_frames(), self.playback_frames()]
		await asyncio.gather(*tasks)

		self.perf_parameters['avg_bitrate'] /= self.totalSegments
		self.perf_parameters['avg_bitrate_change'] /= (self.totalSegments - 1)

		# print(self.manifest_data)
		# print(self.args.urls)
		# print(self.baseUrl)
		# print(self.filename)