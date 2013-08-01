#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# PCEF - Python/Qt Code Editing Framework
# Copyright 2013, Colin Duquesnoy <colin.duquesnoy@gmail.com>
#
# This software is released under the LGPLv3 license.
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
"""
Contains the JediCompletionProvider class implementation.
"""
import jedi
import logging

from pcef.core import Mode, DelayJobRunner
from pcef.qt import QtCore, QtGui


class CalltipsMode(Mode, QtCore.QObject):
    IDENTIFIER = "calltipsMode"
    DESCRIPTION = "Provides functions calltips using the jedi library"

    tooltipDisplayRequested = QtCore.Signal(object, int)
    tooltipHideRequested = QtCore.Signal()

    def __init__(self):
        Mode.__init__(self)
        QtCore.QObject.__init__(self)
        self.__jobRunner = DelayJobRunner(self, nbThreadsMax=1, delay=700)
        self.tooltipDisplayRequested.connect(self.__displayTooltip)
        self.tooltipHideRequested.connect(QtGui.QToolTip.hideText)

    def _onStateChanged(self, state):
        if state:
            self.editor.keyReleased.connect(self.__onKeyReleased)
        else:
            self.editor.keyReleased.disconnect(self.__onKeyReleased)

    def __onKeyReleased(self, event):
        if (event.key() == QtCore.Qt.Key_ParenLeft or
                event.key() == QtCore.Qt.Key_Comma or
                event.key() == QtCore.Qt.Key_Space):
            tc = self.editor.textCursor()
            line = tc.blockNumber() + 1
            col = tc.columnNumber()
            fn = self.editor.filePath
            encoding = self.editor.fileEncoding
            source = self.editor.toPlainText()
            self.__jobRunner.requestJob(self.__execRequest, True,
                                        source, line, col, fn, encoding)
        else:
            QtGui.QToolTip.hideText()

    def __execRequest(self, code, line, col, path, encoding):
        script = jedi.Script(code, line, col, path, encoding)
        call = script.get_in_function_call()
        if call:
            self.tooltipDisplayRequested.emit(call, col)
        else:
            self.tooltipHideRequested.emit()

    def __displayTooltip(self, call, col):
        if not call:
            return
        # create a formatted calltip (current index appear in bold)
        calltip = "<nobr>{0}.{1}(".format(call.module.name, call.call_name)
        for i, param in enumerate(call.params):
            if i != 0:
                calltip += ", "
            if i == call.index:
                calltip += "<b>"
            calltip += str(param.token_list[0])
            if i == call.index:
                calltip += "</b>"
        calltip += ')</nobr>'
        # set tool tip position at the start of the bracket
        charWidth = self.editor.fontMetrics().width('A')
        w_offset = (col - call.bracket_start[1]) * charWidth
        position = QtCore.QPoint(
            self.editor.cursorRect().x() - w_offset,
            self.editor.cursorRect().y())
        position = self.editor.mapToGlobal(position)
        # show tooltip
        QtGui.QToolTip.showText(position, calltip, self.editor)