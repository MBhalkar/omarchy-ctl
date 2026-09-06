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

  property var searchResults: []
  property int displayLimit: 20
  property int searchTotal: 0
  property string searchQuery: ""
  property bool searchRunning: false
  property var allTags: []
  property bool tagsRunning: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  Process {
    id: searchProc
    property var owner: null
    command: ["/home/mb/.local/bin/omarchy-ctl", "search", root.searchQuery, "--json"]
    stdout: StdioCollector {
      id: searchCollector
      waitForEnd: true
      onStreamFinished: {
        var raw = String(text || "").trim()
        if (!raw) {
          root.searchRunning = false
          return
        }
        try {
          var data = JSON.parse(raw)
          root.searchTotal = data.total || 0
          root.searchResults = data.files || []
        } catch (e) {
          console.warn("CTL search parse error:", e)
          root.searchResults = []
          root.searchTotal = 0
        } finally {
          root.searchRunning = false
        }
      }
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) {
        root.searchRunning = false
      }
    }
  }

  Process {
    id: tagsProc
    property var owner: null
    command: ["/home/mb/.local/bin/omarchy-ctl", "tags", "--json"]
    stdout: StdioCollector {
      id: tagsCollector
      waitForEnd: true
      onStreamFinished: {
        var raw = String(text || "").trim()
        if (!raw) {
          root.tagsRunning = false
          return
        }
        try {
          root.allTags = JSON.parse(raw) || []
        } catch (e) {
          console.warn("CTL tags parse error:", e)
          root.allTags = []
        } finally {
          root.tagsRunning = false
        }
      }
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) {
        root.tagsRunning = false
      }
    }
  }

  function open() {
    root.controller.show()
    if (!root.allTags || root.allTags.length === 0) {
      loadTags()
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
    loadTags()
  }

  function doSearch() {
    var query = searchField.text.trim()
    if (!query) return
    root.searchQuery = query
    root.searchRunning = true
    root.searchResults = []
    root.displayLimit = 20
    root.searchTotal = 0
    searchProc.command = ["/home/mb/.local/bin/omarchy-ctl", "search", query, "--json"]
    searchProc.running = true
  }

  function clearSearch() {
    root.searchResults = []
    root.searchTotal = 0
    root.searchQuery = ""
    searchField.text = ""
    Qt.callLater(function() { searchField.forceActiveFocus() })
  }

  function loadTags() {
    if (root.tagsRunning) return
    root.tagsRunning = true
    root.allTags = []
    tagsProc.running = true
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
    contentWidth: panel.fittedContentWidth(Style.space(600))
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

            onAccepted: doSearch()

            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Escape) {
                root.close()
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
          visible: root.searchQuery !== ""
          textFormat: Text.PlainText
          text: root.searchRunning ? "Searching…" : (root.searchTotal + " result" + (root.searchTotal === 1 ? "" : "s") + " for \"" + root.searchQuery + "\"")
          color: Qt.darker(root.bar.foreground, 1.4)
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          font.italic: root.searchRunning
        }

        // ---- Tags row ----
        Row {
          width: parent.width
          spacing: Style.space(6)
          visible: root.allTags.length > 0
          Repeater {
            model: root.allTags
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
          model: root.searchResults.slice(0, root.displayLimit)
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

        // ---- Show More ----
        Rectangle {
          visible: root.searchResults.length > root.displayLimit
          width: parent.width
          height: Style.space(32)
          radius: Style.cornerRadius
          color: showMoreArea.containsMouse ? Style.hoverFillFor(root.bar.foreground, Color.accent) : "transparent"
          border.width: 1
          border.color: Qt.darker(root.bar.foreground, 1.5)

          Text {
            anchors.centerIn: parent
            textFormat: Text.PlainText
            text: "Show more (" + (root.searchResults.length - root.displayLimit) + " remaining)"
            color: root.bar.foreground
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          MouseArea {
            id: showMoreArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.displayLimit += 20
          }
        }

        // ---- Empty state ----
        Text {
          visible: !root.searchRunning && root.searchQuery !== "" && root.searchResults.length === 0
          textFormat: Text.PlainText
          text: "No results"
          color: Qt.darker(root.bar.foreground, 1.5)
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          font.italic: true
        }

        // ---- Idle hint ----
        Text {
          visible: root.searchQuery === "" && !root.searchRunning
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
