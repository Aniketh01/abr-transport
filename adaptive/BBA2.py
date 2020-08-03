from abr import abr
# import json

BBA2_STEADY_STATE = 'steady'
BBA2_STARTUP_STATE = 'startup'
X = 60


class BBA2(abr):
    def __init__(self, manifestData):
        super(BBA2, self).__init__(manifestData)
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

    def NextSegmentQualityIndex(self, playerStats):
        # currBuffer = 0
        # segIdx = -1
        currBuffer = playerStats['currBuffer']
        segIdx = playerStats['segment_Idx']

        if self.state == BBA2_STARTUP_STATE and self.segmentNumber != 0:
            phase = self.checkPhase(currBuffer, segIdx)
            print('phase:',phase)

            segDuration = self.GetSegmentDuration()
            tput = playerStats['lastTput_kbps']
            repID = self.GetCorrespondingQualityIndex(self.ratePrev) - 1 # -1 coz repid starts from 1.
            segSize = self.manifestData['segment_size_bytes'][segIdx][repID]
            deltaB = segDuration - ((segSize * 0.008) / tput)

            if (phase == 0 and deltaB >= 0.875 * segDuration) or (phase == 1 and deltaB >= 0.5 * segDuration):
                rateNext = self.getNextBetterRate(self.ratePrev)
            else:
                rateNext = self.ratePrev
            
            if self.prevBuffer > currBuffer or self.getRateFromChunkMap(currBuffer, segIdx) > rateNext:
                self.state = BBA2_STEADY_STATE
            else:
                self.ratePrev = rateNext
                self.prevBuffer = currBuffer
                self.segmentNumber += 1
                return rateNext

        rateNext = self.getRateFromChunkMap(currBuffer, segIdx)
        self.ratePrev = rateNext
        self.segmentNumber += 1
        return self.GetCorrespondingQualityIndex(rateNext)

    def getRateFromChunkMap(self, currBuffer, segIdx):
        rMax = self.bitrates[-1]
        rMin = self.bitrates[0]

        ratePlus = None
        rateMinus = None

        if self.ratePrev == rMax:
            ratePlus = rMax
        else:
            for i in range(len(self.bitrates)):
                if self.bitrates[i] > self.ratePrev:
                    ratePlus = self.bitrates[i]
                    break
        if self.ratePrev == rMin:
            rateMinus = rMin
        else:
            for i in range(len(self.bitrates) -1, -1, -1):
                if self.bitrates[i] < self.ratePrev:
                    rateMinus = self.bitrates[i]
                    break
        funCurrBuffer = self.fCurrBuffer(currBuffer)
		# print('{}, minus:{}, plus:{}, buffer:{}, corrSize:{}'.format(segIdx, rateMinus, ratePlus, currBuffer, funCurrBuffer))
        rateNext = None

        ratePlusSize = self.manifestData['segment_size_bytes'][segIdx][self.GetCorrespondingQualityIndex(ratePlus)-1]
        rateMinusSize = self.manifestData['segment_size_bytes'][segIdx][self.GetCorrespondingQualityIndex(rateMinus)-1]

        if currBuffer <= self.reservoir:
            rateNext = rMin
        elif currBuffer >= self.reservoir + self.cushion:
            rateNext = rMax
        elif funCurrBuffer >= ratePlusSize:
            rateNext = self.chunkSizeToRate(funCurrBuffer, segIdx)
        elif funCurrBuffer <= rateMinusSize:
            rateNext = self.chunkSizeToRate(funCurrBuffer, segIdx)
        else:
            rateNext = self.ratePrev
        
        return rateNext

    def chunkSizeToRate(self, chunkSize, segIdx):
        minDiff = abs(self.manifestData['segment_size_bytes'][segIdx][0] - chunkSize)
        minDiffIdx = 0

        for i, s in enumerate(self.manifestData['segment_size_bytes'][segIdx]):
            d = abs(s - chunkSize)
            if d < minDiff:
                minDiff = d
                minDiffIdx = i
        
        return self.bitrates[minDiffIdx]


# if __name__ == "__main__":
#     f = open("/home/aniketh/devel/src/abr-over-quic/src/bbb_m.json")
#     manifest = json.load(f)

#     a = BBA2(manifest)
#     q = a.NextSegmentQualityIndex(10)
#     print(q)