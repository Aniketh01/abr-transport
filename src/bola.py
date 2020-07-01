from abr import abr

import math

# calculated from zip files, for each bitrate, from 1 to 5. in kBs
file_sizes = [112.22, 256.50, 577.10, 801.49, 1234.25]

MINIMUM_SAFE_BUFFER = 10
MAXIMUM_TARGET_BUFFER = 30

class Bola(abr):
    def __init__(self, args):
        super(Bola, self).__init__(args)

        bitrates = self.getBitrateList()
        self.bitrates = sorted(bitrates)
        
        # buffer size in s
        self.buffer_size = args.bufferSize

        self.segment_duration = self.GetSegmentDuration()

        self.gp = args.gp



def NextSegmentQualityIndex(self, playerStats):
    self.calculateParameters(MINIMUM_SAFE_BUFFER, MAXIMUM_TARGET_BUFFER, playerStats['segment_Idx'])
