import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "mbhalkar.ctl"

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "\uf02c"
    slotSize: Style.bar.statusSlot
    fontSize: Style.font.body
    tooltipText: "CTL Search"
    onPressed: function(button) {
      if (!root.bar) return
      if (button === Qt.RightButton) {
        root.bar.run("omarchy-shell shell toggle mbhalkar.ctl '{\"reload\":true}'")
      } else {
        root.bar.run("omarchy-shell shell toggle mbhalkar.ctl '{}'")
      }
    }
  }
}