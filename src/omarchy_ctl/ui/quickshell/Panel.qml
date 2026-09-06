import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "CtlModel.js" as CtlModel

Item {
  id: root

  // Injected by omarchy-shell when the overlay is summoned.
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null

  property bool opened: false
  property var searchResults: []
  property int displayLimit: 20
  property int searchTotal: 0
  property string searchQuery: ""
  property bool searchRunning: false
  property var allTags: []
  property bool tagsRunning: false

  readonly property var visibleResults: root.searchResults.slice(0, root.displayLimit)

  // Palette
  property color background: Color.menu.background
  property color foreground: Color.menu.text
  property color border: Color.menu.border
  property color scrim: Color.menu.scrim
  property color accent: Color.accent
  readonly property color dim: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.62)
  readonly property color faint: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.14)
  readonly property color chipFill: Qt.rgba(accent.r, accent.g, accent.b, 0.18)

  readonly property int cardWidth: Math.min(Style.space(1160), panel.width - root.cardPadding * 2)
  readonly property int cardHeight: Math.min(Style.space(820), panel.height - root.cardPadding * 2)
  readonly property int cardPadding: Style.space(12)
  readonly property int headerHeight: Math.max(Style.space(64), Style.font.title + Style.spacing.controlPaddingY * 2)
  readonly property int contentMargin: Style.spacing.panelPadding
  readonly property int ctlRadius: Math.min(8, Style.cornerRadius)

  function readableOn(color) {
    var l = 0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b
    return l > 0.5 ? Qt.rgba(0.05, 0.05, 0.05, 1.0) : Qt.rgba(0.97, 0.97, 0.97, 1.0)
  }

  function open(payloadJson) {
    root.opened = true
    if (payloadJson) {
      try {
        var payload = JSON.parse(payloadJson)
        if (payload && payload.search) {
          searchField.text = String(payload.search)
          Qt.callLater(doSearch)
        }
      } catch (e) {
        console.warn("CTL payload parse error:", e)
      }
    }
    if (payload && payload.reload) {
      reloadTags()
    } else if (!root.allTags || root.allTags.length === 0) {
      loadTags()
    }
    Qt.callLater(function() {
      searchField.forceActiveFocus()
    })
  }

  function close() {
    root.opened = false
  }

  function dismiss() {
    root.close()
    if (root.shell && typeof root.shell.hide === "function") {
      root.shell.hide((root.manifest && root.manifest.id) || "mbhalkar.ctl")
    }
  }

  function reloadTags() {
    loadTags()
    return "ok"
  }

  function ping() {
    return "ok"
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

  Process {
    id: searchProc
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

  PanelWindow {
    id: panel
    visible: root.opened
    anchors {
      top: true
      bottom: true
      left: true
      right: true
    }
    color: "transparent"
    mask: Region {
      item: card
    }
    WlrLayershell.namespace: "omarchy-ctl"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle {
      anchors.fill: parent
      color: root.scrim
    }

    MouseArea {
      anchors.fill: parent
      hoverEnabled: false
      onClicked: root.dismiss()
      z: 1
    }

    BorderSurface {
      id: card
      width: root.cardWidth
      height: root.cardHeight
      radius: root.ctlRadius
      anchors.centerIn: parent
      color: root.background
      borderSpec: Border.surfaceSpec("menu", "border", root.border, Math.max(1, Style.normalBorderWidth))
      z: 2

      MouseArea {
        anchors.fill: parent
        onClicked: {}
        z: 0
      }

      Item {
        id: keyCatcher
        anchors.fill: parent
        z: 3
        focus: true

        Keys.priority: Keys.AfterItem
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Escape) {
            if (searchField.activeFocus && searchField.text.length > 0) {
              root.clearSearch()
            } else {
              root.dismiss()
            }
            event.accepted = true
          } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (!searchField.activeFocus) {
              root.doSearch()
            }
            event.accepted = true
          }
        }

        Column {
          id: layout
          anchors.fill: parent

          // ---- Header ----
          Item {
            id: header
            width: parent.width
            height: root.headerHeight

            Rectangle {
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.bottom: parent.bottom
              height: 1
              color: root.faint
            }

            Text {
              id: headerTitle
              anchors.left: parent.left
              anchors.leftMargin: root.contentMargin
              anchors.verticalCenter: parent.verticalCenter
              textFormat: Text.PlainText
              text: "CTL SEARCH"
              color: root.foreground
              font.family: Style.font.menuFamily
              font.pixelSize: Style.font.heading
              font.bold: true
            }

            Row {
              id: headerButtons
              anchors.right: parent.right
              anchors.rightMargin: root.contentMargin
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.spacing.xs

              Button {
                id: reloadButton
                iconText: "\uf021"
                tooltipText: "Reload tags"
                foreground: root.foreground
                accent: root.accent
                onClicked: root.reloadTags()
              }

              Button {
                id: closeButton
                iconText: "\uf00d"
                tooltipText: "Close"
                foreground: root.foreground
                accent: root.accent
                onClicked: root.dismiss()
              }
            }

            TextField {
              id: searchField
              anchors.left: headerTitle.right
              anchors.right: headerButtons.left
              anchors.leftMargin: Style.spacing.md
              anchors.rightMargin: Style.spacing.md
              anchors.verticalCenter: parent.verticalCenter
              placeholderText: "Search tags and content…"
              foreground: root.foreground
              accent: root.accent
              font.family: Style.font.menuFamily
              font.pixelSize: Style.font.body
              onAccepted: root.doSearch()
            }
          }

          // ---- Body ----
          Item {
            id: body
            width: parent.width
            height: parent.height - header.height

            readonly property int tagsBandHeight: root.allTags.length > 0
              ? Math.min(Style.space(180), Math.max(Style.space(52), height * 0.32))
              : 0

            // Status line
            Text {
              id: statusText
              anchors.top: parent.top
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.topMargin: root.contentMargin
              anchors.leftMargin: root.contentMargin
              anchors.rightMargin: root.contentMargin
              textFormat: Text.PlainText
              text: root.searchRunning ? "Searching…"
                : (root.searchQuery === ""
                    ? root.allTags.length + " tags available · type to search or pick one"
                    : root.searchTotal + " result" + (root.searchTotal === 1 ? "" : "s") + " for \"" + root.searchQuery + "\"")
              color: root.dim
              font.family: Style.font.menuFamily
              font.pixelSize: Style.font.bodySmall
              font.italic: root.searchRunning
              elide: Text.ElideRight
            }

            // Tag chips
            Item {
              id: tagsArea
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.leftMargin: root.contentMargin
              anchors.rightMargin: root.contentMargin
              anchors.top: statusText.bottom
              anchors.topMargin: Style.spacing.sm
              height: parent.tagsBandHeight
              visible: parent.tagsBandHeight > 0
              clip: true

              Flickable {
                id: tagsFlickable
                anchors.fill: parent
                contentWidth: width
                contentHeight: tagsFlow.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height

                Flow {
                  id: tagsFlow
                  width: tagsFlickable.width
                  spacing: Style.spacing.sm

                  Repeater {
                    model: root.allTags
                    delegate: Rectangle {
                      required property var modelData
                      readonly property bool hot: chipArea.containsMouse
                      readonly property color tagBg: CtlModel.tagColor(modelData.name)
                      width: chipText.implicitWidth + Style.space(16)
                      height: Style.space(26)
                      radius: Math.min(13, Style.cornerRadius)
                      color: hot ? tagBg : root.chipFill
                      border.width: hot ? 0 : 1
                      border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.32)

                      Text {
                        id: chipText
                        anchors.centerIn: parent
                        textFormat: Text.PlainText
                        text: modelData.name
                        color: hot ? root.readableOn(tagBg) : root.foreground
                        font.family: Style.font.menuFamily
                        font.pixelSize: Style.font.bodySmall
                      }

                      MouseArea {
                        id: chipArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                          searchField.text = modelData.name
                          root.doSearch()
                        }
                      }
                    }
                  }
                }
              }
            }

            // Results
            Item {
              id: resultsArea
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.leftMargin: root.contentMargin
              anchors.rightMargin: root.contentMargin
              anchors.top: tagsArea.bottom
              anchors.topMargin: Style.spacing.sm
              anchors.bottom: parent.bottom
              anchors.bottomMargin: root.contentMargin

              ListView {
                id: resultsList
                anchors.fill: parent
                model: root.visibleResults
                spacing: Style.space(6)
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height
                footer: resultsList.count > 0 && root.searchResults.length > root.displayLimit
                  ? showMoreFooter
                  : null

                delegate: Rectangle {
                  required property var modelData
                  readonly property string fileName: modelData.filename || modelData.path || ""
                  readonly property string filePath: modelData.path || ""
                  readonly property bool hot: resultArea.containsMouse
                  width: resultsList.width
                  height: Math.max(Style.space(46), resultColumn.implicitHeight + Style.space(10))
                  radius: Math.min(6, Style.cornerRadius)
                  color: hot ? Style.hoverFillFor(root.foreground, root.accent) : "transparent"

                  Column {
                    id: resultColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Style.spacing.md
                    anchors.rightMargin: Style.spacing.md
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Style.space(3)

                    Text {
                      width: parent.width
                      textFormat: Text.PlainText
                      text: fileName
                      color: root.foreground
                      font.family: Style.font.menuFamily
                      font.pixelSize: Style.font.body
                      font.weight: Font.DemiBold
                      elide: Text.ElideRight
                    }

                    Text {
                      width: parent.width
                      textFormat: Text.PlainText
                      text: filePath
                      color: root.dim
                      font.family: Style.font.menuFamily
                      font.pixelSize: Style.font.caption
                      elide: Text.ElideMiddle
                    }
                  }

                  MouseArea {
                    id: resultArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.openFile(filePath)
                  }
                }
              }

              Component {
                id: showMoreFooter
                Rectangle {
                  width: resultsList.width
                  height: Style.space(34)
                  radius: Math.min(6, Style.cornerRadius)
                  color: showMoreArea.containsMouse ? Style.hoverFillFor(root.foreground, root.accent) : "transparent"
                  border.width: 1
                  border.color: root.faint

                  Text {
                    anchors.centerIn: parent
                    textFormat: Text.PlainText
                    text: "Show more (" + (root.searchResults.length - root.displayLimit) + " remaining)"
                    color: root.foreground
                    font.family: Style.font.menuFamily
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
              }

              Text {
                anchors.centerIn: parent
                visible: !root.searchRunning && root.searchQuery !== "" && root.visibleResults.length === 0
                textFormat: Text.PlainText
                text: "No results"
                color: root.dim
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.bodySmall
                font.italic: true
              }

              Text {
                anchors.centerIn: parent
                visible: root.searchQuery === "" && !root.searchRunning && root.allTags.length === 0 && !root.tagsRunning
                textFormat: Text.PlainText
                text: "Loading tags…"
                color: root.dim
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.bodySmall
                font.italic: true
              }
            }
          }
        }
      }
    }
  }
}