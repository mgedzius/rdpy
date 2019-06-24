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


import sys
import os
import argparse
import socket
import collections

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication

from rdpy.ui.qt5 import RDPClientQt
from rdpy.protocol.rdp import rdp
from rdpy.core.error import RDPSecurityNegoFail
from rdpy.core import rss

import rdpy.core.log as log

log._LOG_LEVEL = log.Level.INFO
__desc__ = """
example of use rdpy as rdp client
"""

class RDPClientQtRecorder(RDPClientQt):
    """
    @summary: Widget with record session
    """
    def __init__(self, controller, width, height, rssRecorder):
        """
        @param controller: {RDPClientController} RDP controller
        @param width: {int} width of widget
        @param height: {int} height of widget
        @param rssRecorder: {rss.FileRecorder}
        """
        RDPClientQt.__init__(self, controller, width, height)
        self._screensize = width, height
        self._rssRecorder = rssRecorder

    def onUpdate(self, destLeft, destTop, destRight, destBottom, width, height, bitsPerPixel, isCompress, data):
        """
        @summary: Notify bitmap update
        @param destLeft: {int} xmin position
        @param destTop: {int} ymin position
        @param destRight: {int} xmax position because RDP can send bitmap with padding
        @param destBottom: {int} ymax position because RDP can send bitmap with padding
        @param width: {int} width of bitmap
        @param height: {int} height of bitmap
        @param bitsPerPixel: {int} number of bit per pixel
        @param isCompress: {bool} use RLE compression
        @param data: {str} bitmap data
        """
        #record update
        self._rssRecorder.update(destLeft, destTop, destRight, destBottom, width, height, bitsPerPixel, rss.UpdateFormat.BMP if isCompress else rss.UpdateFormat.RAW, data)
        RDPClientQt.onUpdate(self, destLeft, destTop, destRight, destBottom, width, height, bitsPerPixel, isCompress, data)

    def onReady(self):
        """
        @summary: Call when stack is ready
        """
        self._rssRecorder.screen(self._screensize[0], self._screensize[1], self._controller.getColorDepth())
        RDPClientQt.onReady(self)

    def onClose(self):
        """
        @summary: Call when stack is close
        """
        self._rssRecorder.close()
        RDPClientQt.onClose(self)

    def closeEvent(self, e):
        """
        @summary: Convert Qt close widget event into close stack event
        @param e: QCloseEvent
        """
        self._rssRecorder.close()
        RDPClientQt.closeEvent(self, e)

class RDPClientQtFactory(rdp.ClientFactory):
    """
    @summary: Factory create a RDP GUI client
    """
    def __init__(self, width, height, username, password, domain, fullscreen, keyboardLayout, optimized, security, recodedPath):
        """
        @param width: {integer} width of client
        @param heigth: {integer} heigth of client
        @param username: {str} username present to the server
        @param password: {str} password present to the server
        @param domain: {str} microsoft domain
        @param fullscreen: {bool} show widget in fullscreen mode
        @param keyboardLayout: {str} (fr|en) keyboard layout
        @param optimized: {bool} enable optimized session orders
        @param security: {str} (ssl | rdp | nego)
        @param recodedPath: {str | None} Rss file Path
        """
        self._width = width
        self._height = height
        self._username = username
        self._password = password
        self._domain = domain
        self._fullscreen = fullscreen
        self._keyboardLayout = keyboardLayout
        self._optimized = optimized
        self._nego = security == "nego"
        self._recodedPath = recodedPath
        self._security = rdp.SecurityLevel.RDP_LEVEL_SSL
        if self._nego and ( username != "" and password != "" ):
            self._security = rdp.SecurityLevel.RDP_LEVEL_NLA
        elif security == "rdp":
            self._security = rdp.SecurityLevel.RDP_LEVEL_RDP
        self._w = None

    def buildObserver(self, controller, addr):
        """
        @summary:  Build RFB observer
                    We use a RDPClientQt as RDP observer
        @param controller: build factory and needed by observer
        @param addr: destination address
        @return: RDPClientQt
        """
        #create client observer
        if self._recodedPath is None:
            self._client = RDPClientQt(controller, self._width, self._height)
        else:
            self._client = RDPClientQtRecorder(controller, self._width, self._height, rss.createRecorder(self._recodedPath))
        #create qt widget
        self._w = self._client.getWidget()
        self._w.setWindowTitle('rdpy-rdpclient')
        if self._fullscreen:
            self._w.showFullScreen()
        else:
            self._w.show()

        controller.setUsername(self._username)
        controller.setPassword(self._password)
        controller.setDomain(self._domain)
        controller.setKeyboardLayout(self._keyboardLayout)
        controller.setHostname(socket.gethostname())
        if self._optimized:
            controller.setPerformanceSession()
        controller.setSecurityLevel(self._security)

        return self._client

    def clientConnectionLost(self, connector, reason):
        """
        @summary: Connection lost event
        @param connector: twisted connector use for rdp connection (use reconnect to restart connection)
        @param reason: str use to advertise reason of lost connection
        """
        #try reconnect with basic RDP security
        if reason.type == RDPSecurityNegoFail and self._nego:
            #stop nego
            log.info("due to security nego error back to standard RDP security layer")
            self._nego = False
            self._security = rdp.SecurityLevel.RDP_LEVEL_RDP
            self._client._widget.hide()
            connect.connect()
            return

        log.info("Lost connection : %s"%reason)
        reactor.stop()
        app.exit()

    def clientConnectionFailed(self, connector, reason):
        """
        @summary: Connection failed event
        @param connector: twisted connector use for rdp connection (use reconnect to restart connection)
        @param reason: str use to advertise reason of lost connection
        """
        log.info("Connection failed : %s"%reason)
        reactor.stop()
        app.exit()

def autoDetectKeyboardLayout():
    """
    @summary: try to auto detect keyboard layout
    """
    try:
        if os.name == 'posix':
            from subprocess import check_output
            result = check_output(["setxkbmap", "-print"])
            if b'azerty' in result:
                return "fr"
        elif os.name == 'nt':
            import win32api, win32con, win32process
            from ctypes import windll
            w = windll.user32.GetForegroundWindow()
            tid = windll.user32.GetWindowThreadProcessId(w, 0)
            result = windll.user32.GetKeyboardLayout(tid)
            log.info(result)
            if result == 0x40c040c:
                return "fr"
    except Exception as e:
        log.info("failed to auto detect keyboard layout: {}".format(e))

    return "en"


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
    parser.add_argument('-s', '--security-level', choices=("ssl", "rdp", "nego"), default="rdp", help="set protocol security layer")
    parser.add_argument('--debug', action="store_true", default=False, help="Enable debug output [default : %(default)s]")
    parser.add_argument('--width', type=int, default=1024, help="width of screen [default : %(default)s]")
    parser.add_argument('--height', type=int, default=800, help="height of screen [default : %(default)s]")
    parser.add_argument('--fullscreen', type=bool, default=False, help="enable full screen mode [default : %(default)s]")
    parser.add_argument('--keyboard-layout', type=str, default=autoDetectKeyboardLayout(), choices=("en", "fr"), help="Keyboard layout [default : %(default)s]")
    parser.add_argument('--optimized-session', type=bool, default=False, help="Optimized session (disable costly effect) [default : %(default)s]")
    parser.add_argument('--rss-filepath', default=None, help="Recorded Session Scenario [default : %(default)s]")
    parser.add_argument("target", metavar="IP[:PORT]", type=parse_target_argument, help="Specify the RDP server. If the port is not specified, the default port (tcp/3389) will be used")
    args = parser.parse_args()

    if args.debug:
        log._LOG_LEVEL = log.Level.DEBUG
        log.debug("Debug mode")

    # create application and reactor
    app = QtWidgets.QApplication(sys.argv)

    import qt5reactor
    qt5reactor.install()

    if args.fullscreen:
        width = QtWidgets.QDesktopWidget().screenGeometry().width()
        height = QtWidgets.QDesktopWidget().screenGeometry().height()

    log.info("keyboard layout set to {:s}".format(args.keyboard_layout))

    rdpcli = RDPClientQtFactory(
        args.width,
        args.height,
        args.username,
        args.password,
        args.domain,
        args.fullscreen,
        args.keyboard_layout,
        args.optimized_session,
        args.security_level,
        args.rss_filepath
    )

    from twisted.internet import reactor
    reactor.connectTCP(args.target.ip, int(args.target.port), rdpcli)
    reactor.runReturn()
    app.exec_()