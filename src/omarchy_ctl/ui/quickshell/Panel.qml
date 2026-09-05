import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "CtlModel.js" as CtlModel

Panel {
  id: root
  moduleName: "mbhalkar.ctl"
  ipcTarget: "mbhalkar.ctl"
  manageIpc: false

  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  function open() {
    root.controller.show()
    if (!CtlModel.allTags || CtlModel.allTags.length === 0) {
      CtlModel.loadTags()
    }
    Qt.callLater(function() { searchField.forceActiveFocus() })
  }

  function close() {
    root.controller.hide()
  }

  function toggle() {
    if (root.opened) root.close()
    else root.open()
  }

  function reloadTags() {
    CtlModel.loadTags()
  }

  function doSearch() {
    CtlModel.runSearch(searchField.text)
  }

  function clearSearch() {
    CtlModel.searchResults = []
    CtlModel.searchTotal = 0
    CtlModel.searchQuery = ""
    searchField.text = ""
    Qt.callLater(function() { searchField.forceActiveFocus() })
  }

  function openFile(path) {
    CtlModel.openFile(path)
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: false
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(420))
    contentHeight: panel.fittedContentHeight(ctlColumn.implicitHeight + Style.space(16))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: false
      onCloseRequested: root.close()
      onReturnRequested: doSearch()
    }

    Flickable {
      id: flick
      anchors.fill: parent
      contentWidth: width
      contentHeight: ctlColumn.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      interactive: contentHeight > height

      Column {
        id: ctlColumn
        width: flick.width
        spacing: Style.space(10)

        // ---- Search row ----
        Row {
          width: parent.width
          spacing: Style.space(8)

          TextField {
            id: searchField
            width: parent.width - clearButton.width - Style.space(8)
            placeholderText: "Search files..."
            foreground: root.bar.foreground
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.body

            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Escape) {
                root.close()
                event.accepted = true
              } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                doSearch()
                event.accepted = true
              }
            }
          }

          Rectangle {
            id: clearButton
            width: Style.space(28)
            height: Style.space(28)
            radius: Math.min(4, Style.cornerRadius)
            color: clearArea.containsMouse ? Style.hoverFillFor(root.bar.foreground, Color.accent) : "transparent"

            Text {
              anchors.centerIn: parent
              textFormat: Text.PlainText
              text: "✕"
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
            }

            MouseArea {
              id: clearArea
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: clearSearch()
            }
          }
        }

        // ---- Status line ----
        Text {
          visible: CtlModel.searchQuery !== ""
          textFormat: Text.PlainText
          text: CtlModel.searchRunning ? "Searching…" : (CtlModel.searchTotal + " result" + (CtlModel.searchTotal === 1 ? "" : "s") + " for \"" + CtlModel.searchQuery + "\"")
          color: Qt.darker(root.bar.foreground, 1.4)
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          font.italic: CtlModel.searchRunning
        }

        // ---- Tags row ----
        Row {
          width: parent.width
          spacing: Style.space(6)
          visible: CtlModel.allTags.length > 0
          Repeater {
            model: CtlModel.allTags
            delegate: Rectangle {
              required property var modelData
              required property int index
              width: tagText.implicitWidth + Style.space(12)
              height: Style.space(24)
              radius: Math.min(4, Style.cornerRadius)
              color: index === tagHighlightIndex ? CtlModel.tagColor(modelData.name) : Style.hoverFillFor(root.bar.foreground, Color.accent)

              property int tagHighlightIndex: -1

              Text {
                id: tagText
                anchors.centerIn: parent
                textFormat: Text.PlainText
                text: modelData.name
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }

              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  searchField.text = modelData.name
                  doSearch()
                }
                onPositionChanged: {
                  tagHighlightIndex = index
                }
              }
            }
          }
        }

        // ---- Results ----
        Repeater {
          model: CtlModel.searchResults
          delegate: Rectangle {
            required property var modelData
            required property int index
            width: parent.width
            height: resultColumn.implicitHeight + Style.space(10)
            radius: Style.cornerRadius
            color: resultArea.containsMouse ? Style.hoverFillFor(root.bar.foreground, Color.accent) : "transparent"

            Column {
              id: resultColumn
              width: parent.width
              spacing: Style.space(3)

              Text {
                textFormat: Text.PlainText
                text: modelData.filename || modelData.path || ""
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.body
                elide: Text.ElideRight
                width: parent.width
              }

              Text {
                textFormat: Text.PlainText
                text: modelData.path || ""
                color: Qt.darker(root.bar.foreground, 1.5)
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                elide: Text.ElideMiddle
                width: parent.width
              }
            }

            MouseArea {
              id: resultArea
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.openFile(modelData.path)
            }
          }
        }

        // ---- Empty state ----
        Text {
          visible: !CtlModel.searchRunning && CtlModel.searchQuery !== "" && CtlModel.searchResults.length === 0
          textFormat: Text.PlainText
          text: "No results"
          color: Qt.darker(root.bar.foreground, 1.5)
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          font.italic: true
        }

        // ---- Idle hint ----
        Text {
          visible: CtlModel.searchQuery === "" && !CtlModel.searchRunning
          textFormat: Text.PlainText
          text: "Type to search tags and content"
          color: Qt.darker(root.bar.foreground, 1.5)
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          font.italic: true
        }
      }
    }
  }
}
