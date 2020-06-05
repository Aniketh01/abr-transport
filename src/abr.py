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

    '''
    The throughput rule: bitrate is choosen as per the last throughput.
    The function estimates the quality index for next segment to be downloaded
    on the basis of the throughput rule.
    '''
    def NextSegmentQualityIndex(self, playerStats):
        tput = playerStats["lastTput"]
        #p = manifest.segment_time
        m_bitrate = self.manifestData.get('bitrates_kbps')
        if not tput:
            return 0

        quality_idx = 1
        for bitrate in m_bitrate:
            idx = m_bitrate.index(bitrate)
            if bitrate > tput:
                quality_idx = idx - 1
                break
            quality_idx = idx

        if quality_idx >= 1:
            return quality_idx
        else:
            return 0

    def NextSegmentSize(self, segment_idx, quality):
        size = self.manifestData['segment_size_bytes'][segment_idx][quality]
        return size
