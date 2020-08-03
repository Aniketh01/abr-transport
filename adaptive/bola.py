from abr import abr
import json

import math

# calculated from zip files, for each bitrate, from 1 to 5. in kBs
file_sizes = [691.215, 1229.775, 2764.816, 6220.817]

MINIMUM_SAFE_BUFFER = 10
MAXIMUM_TARGET_BUFFER = 30

class Bola(abr):
    def __init__(self, manifestData):
        super(Bola, self).__init__(manifestData)
        self.manifestData = manifestData

        bitrates = self.getBitrateList()
        self.bitrates = sorted(bitrates)
    
        # buffer size in s
        # self.buffer_size = args.bufferSize
        # self.buffer_size = 100
 

        # default value for gamma variable is set to 5(as said in paper).
        # self.gp = args.gp
        #self.gp = 5

    def calculateParameters(self, min_buffer, target_buffer, seg_idx):
        seg_sizes = self.manifestData['segment_size_bytes'][seg_idx]
        seg_sizes.sort() # sort the list of segments sizes incase it is not sorted in ascending order.
        sM = seg_sizes[0] 

        self.utilities = [math.log(s/sM) for s in seg_sizes]

        self.gp = 1 - self.utilities[0] + (self.utilities[-1] - self.utilities[0]) / (target_buffer / min_buffer - 1)
        self.Vp = min_buffer / (self.utilities[0] + self.gp - 1)

    def NextSegmentQualityIndex(self, playerStats):
        self.calculateParameters(MINIMUM_SAFE_BUFFER, MAXIMUM_TARGET_BUFFER, playerStats['segment_Idx'])
        #self.calculateParameters(MINIMUM_SAFE_BUFFER, MAXIMUM_TARGET_BUFFER, 1)

        level = playerStats['currBuffer']
        # level = 15
        quality = 0
        score = None
        for q in range(len(self.bitrates)):
            s = ((self.Vp * (self.utilities[q] + self.gp) - level) / file_sizes[q])
            if score is None or s >= score:
                quality = q
                score = s

        # print('level:{}, quality:{}, score:{}, i: {}'.format(level, quality, score, i))
        print('quality: {} quality level:{}'.format(self.bitrates[quality], quality))
        return quality


# if __name__ == "__main__":
#     f = open("/home/aniketh/devel/src/abr-over-quic/src/bbb_m.json")
#     manifest = json.load(f)
#     a = Bola(manifest)
#     # for i in range(0, 150, 10):
#     #     q = a.NextSegmentQualityIndex(10, i)
#     q = a.NextSegmentQualityIndex(10)