from abr import abr

BBA2_STEADY_STATE = 'steady'
BBA2_STARTUP_STATE = 'startup'
X = 60


class BBA2(abr):
    def __init__(self, manifestData, args):
        super(BBA2, self).__init__(manifestData, args)
        self.reservoir = 8
        self.normal_reservoir = 8
        self.cushion = 46
        self.manifestData = manifestData
        self.chunksizeMin, self.chunksizeMax = self.findMinMaxChunkSize(self.manifestData['segment_size_bytes'])
        self.k = (self.chunksizeMax - self.chunksizeMin) // self.cushion
        self.state = BBA2_STARTUP_STATE
        self.segmentNumber = 0
        self.bitrates = sorted(self.getBitrateList())
        self.ratePrev = self.bitrates[0]
        self.prevBuffer = 0

    def findMinMaxChunkSize(self, chunkSize):
        minSize = chunkSize[0][0]
        maxSize = chunkSize[0][0]

        for seg in chunkSize:
            for c in seg:
                minSize = min(c, minSize)
                maxSize = max(c, maxSize)

        return minSize, maxSize

    def getNextBetterRate(self, rate):
        # return next bigger bitrate than rate
        for b in self.bitrates:
            if b > rate:
                return b
        return self.bitrates[-1]

    def checkPhase(self, currBuffer, segIdx):
        #  return phase for startup algorithm from paper.

        # if self.prevBuffer > currBuffer or self.getRateFromChunkMap(currBuffer, segIdx) > self.getNextBetterRate(self.ratePrev):
        # 	return 2 # means need to break from startup algorithm
        if currBuffer >= self.reservoir + self.cushion:
            return 1  # can step up rate even download speed is twice the play speed
        else:
            return 0  # step up rate if download speed is at least 0.875 times of play speed

    def adjustingReservoir(self, segIdx):
        expected_size_consumption = X * self.bitrates[0]
        real_size_consumption = 0
        segments_in_X = int(X / self.GetSegmentDuration())

        for i in range(segIdx, segIdx + segments_in_X):
            if i < self.GetTotalSegments():
                real_size_consumption += self.manifestData['segment_size_bytes'][i][0]

        adjusted = self.normal_reservoir + \
            ((real_size_consumption * 8) -
             expected_size_consumption) / self.bitrates[0]

        self.reservoir = adjusted
        # print('new reservior', self.reservoir)

    def fCurrBuffer(self, currBuffer):
        if currBuffer < self.reservoir:
            return self.chunksizeMin
        elif currBuffer > self.reservoir + self.cushion:
            return self.chunksizeMax
        else:
            return (currBuffer - self.reservoir) * self.k + self.chunksizeMin