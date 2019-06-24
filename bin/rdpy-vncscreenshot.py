#!/usr/bin/python3
#
# Copyright (c) 2014-2015 Sylvain Peyrefitte
#
# This file is part of rdpy.
#
# rdpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

__desc__="""
example of use rdpy
take screenshot of login page
"""

import sys, os, argparse, collections, tempfile
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from rdpy.ui.qt5 import RFBClientQt, qtImageFormatFromRFBPixelFormat
from rdpy.protocol.rfb import rfb

import rdpy.core.log as log
log._LOG_LEVEL = log.Level.INFO


class RFBScreenShotFactory(rfb.ClientFactory):
    """
    @summary: Factory for screenshot exemple
    """
    __INSTANCE__ = 0
    def __init__(self, password, path):
        """
        @param password: password for VNC authentication
        @param path: path of output screenshot
        """
        RFBScreenShotFactory.__INSTANCE__ += 1
        self._path = path
        self._password = password

    def clientConnectionLost(self, connector, reason):
        """
        @summary: Connection lost event
        @param connector: twisted connector use for rfb connection (use reconnect to restart connection)
        @param reason: str use to advertise reason of lost connection
        """
        log.warning("connection lost : %s"%reason)
        RFBScreenShotFactory.__INSTANCE__ -= 1
        if(RFBScreenShotFactory.__INSTANCE__ == 0):
            reactor.stop()
            app.exit()

    def clientConnectionFailed(self, connector, reason):
        """
        @summary: Connection failed event
        @param connector: twisted connector use for rfb connection (use reconnect to restart connection)
        @param reason: str use to advertise reason of lost connection
        """
        log.error("connection failed : %s"%reason)
        RFBScreenShotFactory.__INSTANCE__ -= 1
        if(RFBScreenShotFactory.__INSTANCE__ == 0):
            reactor.stop()
            app.exit()


    def buildObserver(self, controller, addr):
        """
        @summary: build ScreenShot observer
        @param controller: RFBClientController
        @param addr: address of target
        """
        class ScreenShotObserver(rfb.RFBClientObserver):
            """
            @summary: observer that connect, cache every image received and save at deconnection
            """
            def __init__(self, controller, path):
                """
                @param controller: RFBClientController
                @param path: path of output screenshot
                """
                rfb.RFBClientObserver.__init__(self, controller)
                self._path = path
                self._buffer = None

            def onUpdate(self, width, height, x, y, pixelFormat, encoding, data):
                """
                Implement RFBClientObserver interface
                @param width: width of new image
                @param height: height of new image
                @param x: x position of new image
                @param y: y position of new image
                @param pixelFormat: pixefFormat structure in rfb.message.PixelFormat
                @param encoding: encoding type rfb.message.Encoding
                @param data: image data in accordance with pixel format and encoding
                """
                imageFormat = qtImageFormatFromRFBPixelFormat(pixelFormat)
                if imageFormat is None:
                    log.error("Receive image in bad format")
                    return
                image = QtGui.QImage(data, width, height, imageFormat)
                with QtGui.QPainter(self._buffer) as qp:
                    qp.drawImage(x, y, image, 0, 0, width, height)

                self._controller.close()

            def onReady(self):
                """
                @summary: callback use when RDP stack is connected (just before received bitmap)
                """
                log.info("connected %s"%addr)
                width, height = self._controller.getScreen()
                self._buffer = QtGui.QImage(width, height, QtGui.QImage.Format_RGB32)

            def onClose(self):
                """
                @summary: callback use when RDP stack is closed
                """
                log.info("save screenshot into %s"%self._path)
                self._buffer.save(self._path)

        controller.setPassword(self._password)
        return ScreenShotObserver(controller, self._path)


def parse_target_argument(x):
    Target = collections.namedtuple('Target', ['ip', 'port'])
    if ':' in x:
        ip, port = x.split(':')
    else:
        ip, port = x, "5900"
    return Target(ip, int(port))


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description = __desc__,
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('--debug', action="store_true", default=False, help="Enable debug output [default : %(default)s]")
    parser.add_argument('-p', '--password', type=str, default="", help="password")
    parser.add_argument('--output-path', type=str, default=tempfile.gettempdir(), help="the output directory [default : %(default)s]")
    parser.add_argument("targets", metavar="IP[:PORT]", type=parse_target_argument, help="Specify the VNC server(s). If the port is not specified, the default port (tcp/5900) will be used")
    args = parser.parse_args()

    if args.debug:
        log._LOG_LEVEL = log.Level.DEBUG
        log.debug("Debug mode")

    #create application
    app = QApplication(sys.argv)

    #add qt5 reactor
    import qt5reactor
    qt5reactor.install()

    from twisted.internet import reactor

    for arg in args.targets:
        vnccli = RFBScreenShotFactory(args.password, os.sep.join([args.path, "{:s}.jpg".format(arg.ip)]))
        reactor.connectTCP(args.target.ip, args.target.port, vnccli)

    reactor.runReturn()
    app.exec_()