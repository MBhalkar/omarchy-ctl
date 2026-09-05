import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "mbhalkar.ctl"

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

  function open() {
    if (panelLoader.item && panelLoader.item.open) panelLoader.item.open()
  }

  function close() {
    if (panelLoader.item && panelLoader.item.close) panelLoader.item.close()
  }

  function toggle() {
    if (root.opened) root.close()
    else root.open()
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      if (panelLoader.item) {
        panelLoader.item.hostWidget = root
      }
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "\uf02c"
    slotSize: Style.bar.statusSlot
    fontSize: Style.font.body
    tooltipText: "CTL Search"
    onPressed: function(button) {
      if (button === Qt.RightButton) {
        if (panelLoader.item && panelLoader.item.reloadTags) panelLoader.item.reloadTags()
      } else {
        root.toggle()
      }
    }
  }
}
