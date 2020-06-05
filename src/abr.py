# super class for adaptive alogorithms
# This class implements basic throughput rule


class abr:
    def __init__(self, manifestData):
        self.manifestData = manifestData
    
    def getBitrateList(self):
        manifest_bitrate = self.manifestData.get('bitrates_kbps')
        bitrateList = []
        for bitrate in manifest_bitrate:
            bitrateList.append(int(bitrate))
        return bitrateList