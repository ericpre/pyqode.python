# -*- coding: utf-8 -*-
"""
Contains the go to assignments mode.
"""
import logging
import os
from PyQt4 import QtCore, QtGui
from pyqode.core import frontend
from pyqode.core.frontend import Mode
from pyqode.core.frontend.modes import WordClickMode
from pyqode.python.backend import workers


def _logger():
    return logging.getLogger(__name__)


class Assignment(object):
    """
    Assignment definition.
    """
    def __init__(self, path, line, column, full_name):
        #: Module path
        if path:
            path = path.replace(".pyc", ".py")
        self.module_path = path
        #: Line number
        self.line = line
        #: Column number
        self.column = column
        #: Assignement full name
        self.full_name = full_name

    def __str__(self):
        if self.line and self.column:
            return "%s (%s, %s)" % (self.full_name, self.line, self.column)
        return self.full_name

    def __repr__(self):
        return "Definition(%r, %r, %r, %r)" % (self.module_path, self.line,
                                               self.column, self.full_name)


class GoToAssignmentsMode(Mode, QtCore.QObject):
    """
    Goes to the assignments (using jedi.Script.goto_assignments). If there are
    more than one assignments, an input dialog is used to ask the user to
    choose the desired assignment.

    This mode will emit
    :attr:`pyqode.python.frontend.modes.GoToAssignmentsMode.out_of_doc` if the
    definition can not be reached in the current document. IDE will typically
    open a new editor tab and go to the definition.

    """
    #: Signal emitted when the definition cannot be reached in the current
    #: document
    out_of_doc = QtCore.pyqtSignal(Assignment)

    #: Signal emitted when no results could be found.
    no_results_found = QtCore.pyqtSignal()

    def __init__(self):
        Mode.__init__(self)
        QtCore.QObject.__init__(self)
        self._pending = False
        self.action_goto = QtGui.QAction("Go to assignments", self)
        self.action_goto.setShortcut("F2")
        self.action_goto.triggered.connect(self.request_goto)

    def _on_install(self, editor):
        super()._on_install(editor)

    def _on_state_changed(self, state):
        if state:
            frontend.get_mode(self.editor, WordClickMode).word_clicked.connect(
                self.request_goto)
            self.sep = self.editor.add_separator()
            self.editor.add_action(self.action_goto)
        else:
            frontend.get_mode(
                self.editor, WordClickMode).word_clicked.disconnect(
                    self.request_goto)
            self.editor.remove_action(self.action_goto)
            self.editor.remove_action(self.sep)

    def request_goto(self, tc=None):
        """
        Request a go to assignment.

        :param tc: Text cursor which contains the text that we must look for
                   its assignment. Can be None to go to the text that is under
                   the text cursor.
        :type tc: QtGui.QTextCursor
        """
        if not tc:
            tc = frontend.word_under_cursor(self.editor)
        if not self._pending:
            request_data = {
                'code': self.editor.toPlainText(),
                'line': tc.blockNumber() + 1,
                'column': tc.columnNumber(),
                'path': self.editor.file_path,
                'encoding': self.editor.file_encoding
            }
            frontend.request_work(self.editor,
                                  workers.goto_assignments,
                                  request_data,
                                  on_receive=self._on_results_available)
            self._pending = True
        self.editor.set_mouse_cursor(QtCore.Qt.WaitCursor)

    def _goto(self, definition):
        if not self.editor.file_path:
            fp = ''
        else:
            fp = os.path.normpath(self.editor.file_path.replace(".pyc", ".py"))
        if definition.module_path == fp:
            line = definition.line
            col = definition.column
            _logger().debug("Go to %s" % definition)
            frontend.goto_line(self.editor, line, move=True, column=col)
        else:
            _logger().debug("Out of doc: %s" % definition)
            self.out_of_doc.emit(definition)

    def _unique(self, seq):
        """
        Not performant but works.
        """
        # order preserving
        checked = []
        for e in seq:
            present = False
            for c in checked:
                if str(c) == str(e):
                    present = True
                    break
            if not present:
                checked.append(e)
        return checked

    def _on_results_available(self, status, definitions):
        if status:
            self.editor.set_mouse_cursor(QtCore.Qt.IBeamCursor)
            self._pending = False
            definitions = [Assignment(path, line, col, full_name)
                           for path, line, col, full_name in definitions]
            definitions = self._unique(definitions)
            _logger().debug("Got %r" % definitions)
            if len(definitions) == 1:
                definition = definitions[0]
                if definition:
                    self._goto(definition)
            elif len(definitions) > 1:
                _logger().debug(
                    "More than 1 assignments in different modules, user "
                    "need to make a choice: %s" % definitions)
                def_str, result = QtGui.QInputDialog.getItem(
                    self.editor, "Choose a definition",
                    "Choose the definition you want to go to:",
                    [str(d) for d in definitions])
                if result:
                    for definition in definitions:
                        if definition and str(definition) == def_str:
                            self._goto(definition)
                            return
            else:
                _logger().info("GoToAssignments: No results found")
                self.no_results_found.emit()