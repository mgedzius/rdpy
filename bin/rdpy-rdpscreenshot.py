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

__desc__ = """
example of use rdpy
take screenshot of login page
"""

import os, sys, argparse, tempfile, collections

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication
from rdpy.protocol.rdp import rdp
from rdpy.ui.qt5 import RDPBitmapToQtImage
from rdpy.core.error import RDPSecurityNegoFail

import rdpy.core.log as log

# set log level
log._LOG_LEVEL = log.Level.INFO


class RDPScreenShotFactory(rdp.ClientFactory):
    """
    @summary: Factory for screenshot exemple
    """
    __INSTANCE__ = 0
    __STATE__ = []

    def __init__(self, reactor, app, args, path):
        """
        @param reactor: twisted reactor
        @param width: {integer} width of screen
        @param height: {integer} height of screen
        @param path: {str} path of output screenshot
        @param timeout: {float} close connection after timeout s without any updating
        """
        RDPScreenShotFactory.__INSTANCE__ += 1
        self._reactor = reactor
        self._app = app
        self._username = args.username
        self._password = args.password
        self._domain = args.domain
        self._width = args.width
        self._height = args.height
        self._path = path
        self._timeout = args.timeout
        self._security = rdp.SecurityLevel.RDP_LEVEL_RDP if args.security_level == "rdp" else rdp.SecurityLevel.RDP_LEVEL_SSL

    def clientConnectionLost(self, connector, reason):
        """
        @summary: Connection lost event
        @param connector: twisted connector use for rdp connection (use reconnect to restart connection)
        @param reason: str use to advertise reason of lost connection
        """
        if reason.type == RDPSecurityNegoFail and self._security != rdp.SecurityLevel.RDP_LEVEL_RDP:
            log.info("due to RDPSecurityNegoFail try standard security layer")
            self._security = rdp.SecurityLevel.RDP_LEVEL_RDP
            connector.connect()
            return

        log.warning("connection lost : %s" % reason)
        RDPScreenShotFactory.__STATE__.append((connector.host, connector.port, reason))
        RDPScreenShotFactory.__INSTANCE__ -= 1
        if(RDPScreenShotFactory.__INSTANCE__ == 0):
            self._reactor.stop()
            self._app.exit()

    def clientConnectionFailed(self, connector, reason):
        """
        @summary: Connection failed event
        @param connector: twisted connector use for rdp connection (use reconnect to restart connection)
        @param reason: str use to advertise reason of lost connection
        """
        log.error("connection failed : %s" % reason)
        RDPScreenShotFactory.__STATE__.append((connector.host, connector.port, reason))
        RDPScreenShotFactory.__INSTANCE__ -= 1
        if(RDPScreenShotFactory.__INSTANCE__ == 0):
            self._reactor.stop()
            self._app.exit()

    def buildObserver(self, controller, addr):
        """
        @summary: build ScreenShot observer
        @param controller: RDPClientController
        @param addr: address of target
        """
        class ScreenShotObserver(rdp.RDPClientObserver):
            """
            @summary: observer that connect, cache every image received and save at deconnection
            """
            def __init__(self, controller, width, height, path, timeout, reactor):
                """
                @param controller: {RDPClientController}
                @param width: {integer} width of screen
                @param height: {integer} height of screen
                @param path: {str} path of output screenshot
                @param timeout: {float} close connection after timeout s without any updating
                @param reactor: twisted reactor
                """
                rdp.RDPClientObserver.__init__(self, controller)
                self._buffer = QtGui.QImage(width, height, QtGui.QImage.Format_RGB32)
                self._path = path
                self._timeout = timeout
                self._startTimeout = False
                self._reactor = reactor

            def onUpdate(self, destLeft, destTop, destRight, destBottom, width, height, bitsPerPixel, isCompress, data):
                """
                @summary: callback use when bitmap is received
                """
                image = RDPBitmapToQtImage(width, height, bitsPerPixel, isCompress, data);
                with QtGui.QPainter(self._buffer) as qp:
                    qp.drawImage(destLeft, destTop, image, 0, 0, destRight - destLeft + 1, destBottom - destTop + 1)
                if not self._startTimeout:
                    self._startTimeout = False
                    self._reactor.callLater(self._timeout, self.checkUpdate)

            def onReady(self):
                """
                @summary: callback use when RDP stack is connected (just before received bitmap)
                """
                log.info("connected %s" % addr)

            def onSessionReady(self):
                """
                @summary: Windows session is ready
                @see: rdp.RDPClientObserver.onSessionReady
                """
                pass

            def onClose(self):
                """
                @summary: callback use when RDP stack is closed
                """
                log.info("save screenshot into %s" % self._path)
                self._buffer.save(self._path)

            def checkUpdate(self):
                self._controller.close();

        controller.setUsername(self._username)
        controller.setPassword(self._password)
        controller.setDomain(self._domain)
        controller.setKeyboardLayout("en")
        controller.setSecurityLevel(self._security)
        controller.setScreen(self._width, self._height);
        return ScreenShotObserver(controller, self._width, self._height, self._path, self._timeout, self._reactor)


def main(args):
    """
    @summary: main algorithm
    @param height: {integer} height of screenshot
    @param width: {integer} width of screenshot
    @param timeout: {float} in sec
    @param hosts: {list(str(ip[:port]))}
    @return: {list(tuple(ip, port, Failure instance)} list of connection state
    """

    # create application and reactor
    app = QtWidgets.QApplication(sys.argv)

    #add qt5 reactor
    import qt5reactor
    qt5reactor.install()

    from twisted.internet import reactor

    for host in args.targets:
        outfile = os.sep.join([args.output_path, "{:s}.jpg".format(host.ip)])
        rdpcli = RDPScreenShotFactory(reactor, app, args, outfile)
        reactor.connectTCP(host.ip, host.port, rdpcli)

    reactor.runReturn()
    app.exec_()
    return RDPScreenShotFactory.__STATE__


def parse_target_argument(x):
    Target = collections.namedtuple('Target', ['ip', 'port'])
    if ':' in x:
        ip, port = x.split(':')
    else:
        ip, port = x, "3389"
    return Target(ip, int(port))




if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description = __desc__,
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-u', '--username', type=str, default="", help="username")
    parser.add_argument('-p', '--password', type=str, default="", help="password")
    parser.add_argument('-d', '--domain', type=str, default="", help="domain")
    parser.add_argument('-s', '--security-level', choices=("ssl", "rdp"), default="rdp", help="set protocol security layer")
    parser.add_argument('--debug', action="store_true", default=False, help="Enable debug output [default : %(default)s]")
    parser.add_argument('--width', type=int, default=1024, help="width of screen [default : %(default)s]")
    parser.add_argument('--height', type=int, default=800, help="height of screen [default : %(default)s]")
    parser.add_argument('--timeout', type=float, default=5.0, help="timeout before snap [default : %(default)s]")
    parser.add_argument('--output-path', type=str, default=tempfile.gettempdir(), help="the output directory [default : %(default)s]")
    parser.add_argument("targets", metavar="IP[:PORT]", nargs='+', type=parse_target_argument, help="Specify the RDP server(s). If the port is not specified, the default port (tcp/3389) will be used")
    args = parser.parse_args()

    if args.debug:
        log._LOG_LEVEL = log.Level.DEBUG
        log.debug("Debug mode")

    main(args)
