#!/usr/bin/python
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
example of use rdpy as VNC client
"""

import sys, os, argparse, collections
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from rdpy.ui.qt5 import RFBClientQt
from rdpy.protocol.rfb import rfb

import rdpy.core.log as log
log._LOG_LEVEL = log.Level.INFO


class RFBClientQtFactory(rfb.ClientFactory):
    """
    @summary: Factory create a VNC GUI client
    """
    def __init__(self, password):
        """
        @param password: password for VNC authentication
        """
        self._password = password

    def buildObserver(self, controller, addr):
        """
        @summary: Build RFB Client observer
        @param controller: build by factory
        @param addr: destination
        """
        #set password
        controller.setPassword(self._password)
        #create client observer
        client = RFBClientQt(controller)
        #create qt widget
        self._w = client.getWidget()
        self._w.setWindowTitle('rdpy-vncclient')
        self._w.show()
        return client

    def clientConnectionLost(self, connector, reason):
        """
        @summary: Connection lost event
        @param connector: twisted connector use for vnc connection (use reconnect to restart connection)
        @param reason: str use to advertise reason of lost connection
        """
        QMessageBox.warning(self._w, "Warning", "Lost connection : %s"%reason)
        reactor.stop()
        app.exit()

    def clientConnectionFailed(self, connector, reason):
        """
        @summary: Connection failed event
        @param connector: twisted connector use for vnc connection (use reconnect to restart connection)
        @param reason: str use to advertise reason of lost connection
        """
        QMessageBox.warning(self._w, "Warning", "Connection failed : %s"%reason)
        reactor.stop()
        app.exit()


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
    parser.add_argument("target", metavar="IP[:PORT]", type=parse_target_argument, help="Specify the VNC server. If the port is not specified, the default port (tcp/5900) will be used")
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
    reactor.connectTCP(args.target.ip, args.target.port, RFBClientQtFactory(args.password))
    reactor.runReturn()
    app.exec_()