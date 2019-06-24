from rdpy.core.type import CompositeType, CallableValue, UInt16Le, UInt32Le, String, sizeof
from rdpy.core.layer import Layer, LayerAutomata
from rdpy.protocol.rdp.t125.gcc import ChannelDef, ChannelOptions
from rdpy.protocol.rdp.pdu.data import DataPDU
from rdpy.protocol.rdp.pdu.layer import PDULayer
from rdpy.protocol.rdp.t125.mcs import IStreamSender, MCSLayer
from rdpy.protocol.rdp.sec import SecurityFlag
from rdpy.protocol.rdp.tpkt import IFastPathListener
import rdpy.protocol.rdp.sec as sec
import rdpy.core.log as log

#
# 2.2.6.1.1 Channel PDU Header (CHANNEL_PDU_HEADER)
# -> flags
#
class ChannelHeaderFlag:
    CHANNEL_FLAG_FIRST = 0x00000001
    CHANNEL_FLAG_LAST = 0x00000002
    CHANNEL_FLAG_SHOW_PROTOCOL = 0x00000010
    CHANNEL_FLAG_SUSPEND = 0x00000020
    CHANNEL_FLAG_RESUME = 0x00000040
    CHANNEL_FLAG_SHADOW_PERSISTENT = 0x00000080
    CHANNEL_PACKET_COMPRESSED = 0x00200000
    CHANNEL_PACKET_AT_FRONT = 0x00400000
    CHANNEL_PACKET_FLUSHED = 0x00800000


#
# 2.2.6.1.1 Channel PDU Header (CHANNEL_PDU_HEADER)
#
class VirtualChannelPDU(CompositeType):
    def __init__(self, data=b""):
        CompositeType.__init__(self)
        self.length = UInt32Le(lambda:(sizeof(self) - 8))
        self.flags = UInt32Le()
        self.virtualChannelData = String(data, readLen = CallableValue(lambda: self.length))


class VirtualChannelLayer(LayerAutomata, IStreamSender):
    def __init__(self, _secLayer):
        LayerAutomata.__init__(self, None)
        self._secLayer = _secLayer

    def flush(self):
        # Hack: Twisted seems to be buffering data, this function forces the socket write
        twisted_socket = self._transport._mcs._transport._transport.transport.transport
        twisted_socket.doWrite()

    def sendFlaggedData(self, flag, data, _total_length=None, _chunk_length=None):
        pduHeader = VirtualChannelPDU()
        if _total_length:
            pduHeader.length.value = _total_length
        if _chunk_length:
            pduHeader.virtualChannelData._readLen.value = _chunk_length
        pduHeader.flags.value = flag
        pduHeader.virtualChannelData.value = data
        self._transport.send(pduHeader)
        self.flush()

    def send(self, data):
        self.sendFlaggedData(ChannelHeaderFlag.CHANNEL_FLAG_FIRST | ChannelHeaderFlag.CHANNEL_FLAG_LAST, data)

    def sendEncryptedData(self, data):
        self._secLayer.sendFlagged(SecurityFlag.SEC_ENCRYPT, VirtualChannelPDU(data), self._transport)
        self.flush()

    def sendEncryptedFlaggedData(self, flag, data, _total_length=None, _chunk_length=None, _secure_checksum=False):
        pdu = VirtualChannelPDU()
        if _total_length:
            pdu.length.value = _total_length
        if _chunk_length:
            pdu.virtualChannelData._readLen.value = _chunk_length
        pdu.flags.value = flag
        pdu.virtualChannelData.value = data
        secLayerFlags = SecurityFlag.SEC_ENCRYPT
        if _secure_checksum:
            secLayerFlags |= SecurityFlag.SEC_SECURE_CHECKSUM
        self._secLayer.sendFlagged(secLayerFlags, pdu, self._transport)
        self.flush()


class Client(VirtualChannelLayer):
    def __init__(self, secLayer, channelName, channelOptions):
        VirtualChannelLayer.__init__(self, secLayer)
        self._definition = ChannelDef(channelName, channelOptions)

    def connect(self):
        pass

    def close(self):
        self._transport.close()

    def recvChannelData(self, stream):
        pdu = VirtualChannelPDU()
        stream.readType(pdu)

    def __str__(self):
        return self._definition.name.value.decode("utf-8")
