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
  property int pageSize: 50
  property int currentPage: 1
  property int pendingPage: 1
  property int searchTotal: 0
  property string searchQuery: ""
  property bool searchRunning: false
  property bool pageFetching: false
  property var pageCache: ({})
  property string exportStatus: ""
  property string exportPath: ""
  property var allTags: []
  property bool tagsRunning: false

  readonly property int totalPages: root.searchTotal > 0 ? Math.max(1, Math.ceil(root.searchTotal / Math.max(1, root.pageSize))) : 0

  readonly property var visibleResults: root.searchResults

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
    root.pageCache = {}
    root.currentPage = 0
    root.pendingPage = 1
    root.searchTotal = 0
    root.searchResults = []
    root.exportStatus = ""
    root.exportPath = root.defaultExportPath()
    root.fetchPage(1)
  }

  function fetchPage(n) {
    if (root.pageFetching) return
    n = Math.max(1, n)
    var cached = root.pageCache[String(n)]
    if (cached !== undefined) {
      root.currentPage = n
      root.pendingPage = n
      root.searchResults = cached
      return
    }
    root.pageFetching = true
    root.searchRunning = true
    root.pendingPage = n
    searchProc.command = ["/home/mb/.local/bin/omarchy-ctl", "search", root.searchQuery, "--json", "--limit", String(root.pageSize), "--offset", String((n - 1) * root.pageSize)]
    searchProc.running = true
  }

  function goToPage(n) {
    n = Math.max(1, Math.min(n, root.totalPages))
    if (n === root.currentPage) return
    root.fetchPage(n)
  }

  function gotoPrev() {
    root.goToPage(root.currentPage - 1)
  }

  function gotoNext() {
    root.goToPage(root.currentPage + 1)
  }

  function onPageSizeChosen(v) {
    var n = parseInt(v, 10)
    if (isNaN(n) || n < 1 || n === root.pageSize) return
    root.pageSize = n
    root.pageCache = {}
    if (root.searchQuery) {
      root.currentPage = 0
      root.pendingPage = 1
      root.fetchPage(1)
    }
  }

  function pageSizeOptions() {
    return CtlModel.pageSizeOptions(root.searchTotal)
  }

  function preferredPageSize() {
    return CtlModel.preferredPageSize(root.searchTotal)
  }

  function ensurePageSizeValid() {
    if (root.searchTotal <= 0) return
    var opts = root.pageSizeOptions()
    var found = false
    for (var i = 0; i < opts.length; i++) {
      if (opts[i].value === String(root.pageSize)) {
        found = true
        break
      }
    }
    if (!found) {
      root.pageSize = root.preferredPageSize()
      root.pageCache = {}
    }
  }

  function defaultExportPath() {
    var home = Quickshell.env("HOME") || "/home/mb"
    return home + "/Downloads/ctl_export_" + CtlModel.sanitizeName(root.searchQuery) + ".xlsx"
  }

  function exportToExcel() {
    if (!root.searchQuery || root.searchRunning) return
    root.exportStatus = "Exporting…"
    exportProc.command = ["/home/mb/.local/bin/omarchy-ctl", "export", root.searchQuery, "--output", root.exportPath]
    exportProc.running = true
  }

  function clearSearch() {
    root.searchResults = []
    root.searchTotal = 0
    root.searchQuery = ""
    root.pageCache = {}
    root.currentPage = 0
    root.pendingPage = 1
    root.exportStatus = ""
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
          root.pageFetching = false
          root.searchRunning = false
          return
        }
        try {
          var data = JSON.parse(raw)
          var page = root.pendingPage || 1
          root.pageCache[String(page)] = data.files || []
          root.currentPage = page
          root.searchResults = data.files || []
          root.searchTotal = data.total || 0
          root.ensurePageSizeValid()
        } catch (e) {
          console.warn("CTL search parse error:", e)
          root.searchResults = []
          root.searchTotal = 0
        } finally {
          root.pageFetching = false
          root.searchRunning = false
        }
      }
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) {
        root.pageFetching = false
        root.searchRunning = false
      }
    }
  }

  Process {
    id: exportProc
    command: ["/home/mb/.local/bin/omarchy-ctl", "export", root.searchQuery, "--output", root.exportPath]
    stdout: StdioCollector {
      id: exportCollector
      waitForEnd: true
      onStreamFinished: {
        var raw = String(text || "").trim()
        if (raw) {
          root.exportStatus = raw
        }
      }
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) {
        root.exportStatus = "Export failed"
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
          } else if (event.key === Qt.Key_PageUp) {
            root.gotoPrev()
            event.accepted = true
          } else if (event.key === Qt.Key_PageDown) {
            root.gotoNext()
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
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: pagerBar.top
                anchors.bottomMargin: Style.spacing.sm
                model: root.visibleResults
                spacing: Style.space(6)
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height

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

              // ---- Pager + per-page + export ----
              Item {
                id: pagerBar
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Style.space(56)

                Button {
                  id: prevButton
                  anchors.left: parent.left
                  anchors.verticalCenter: parent.verticalCenter
                  iconText: "\uf104"
                  tooltipText: "Previous page"
                  foreground: root.foreground
                  accent: root.accent
                  opacity: root.currentPage > 1 ? 1 : 0.35
                  enabled: root.currentPage > 1
                  onClicked: root.gotoPrev()
                }

                Text {
                  id: pageIndicator
                  anchors.left: prevButton.right
                  anchors.leftMargin: Style.spacing.md
                  anchors.verticalCenter: parent.verticalCenter
                  textFormat: Text.PlainText
                  text: root.searchTotal > 0
                    ? "Page " + root.currentPage + " / " + root.totalPages + " · " + root.searchTotal + " result" + (root.searchTotal === 1 ? "" : "s")
                    : ""
                  color: root.dim
                  font.family: Style.font.menuFamily
                  font.pixelSize: Style.font.bodySmall
                }

                Button {
                  id: nextButton
                  anchors.left: pageIndicator.right
                  anchors.leftMargin: Style.spacing.md
                  anchors.verticalCenter: parent.verticalCenter
                  iconText: "\uf105"
                  tooltipText: "Next page"
                  foreground: root.foreground
                  accent: root.accent
                  opacity: root.currentPage < root.totalPages ? 1 : 0.35
                  enabled: root.currentPage < root.totalPages
                  onClicked: root.gotoNext()
                }

                Button {
                  id: exportButton
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  iconText: "\uf1c1"
                  tooltipText: "Export all results to Excel"
                  foreground: root.foreground
                  accent: root.accent
                  onClicked: root.exportToExcel()
                }

                Dropdown {
                  id: pageSizeDropdown
                  anchors.right: exportStatusLabel.left
                  anchors.rightMargin: Style.spacing.md
                  anchors.verticalCenter: parent.verticalCenter
                  width: Style.space(110)
                  label: "Per page"
                  foreground: root.foreground
                  background: root.background
                  popupBorder: root.border
                  accent: root.accent
                  fontFamily: Style.font.menuFamily
                  options: root.pageSizeOptions()
                  value: String(root.pageSize)
                  onChanged: function(v) {
                    root.onPageSizeChosen(v)
                  }
                }

                Text {
                  id: exportStatusLabel
                  anchors.right: exportButton.left
                  anchors.rightMargin: Style.spacing.md
                  anchors.verticalCenter: parent.verticalCenter
                  textFormat: Text.PlainText
                  visible: root.exportStatus !== ""
                  text: root.exportStatus
                  color: root.dim
                  font.family: Style.font.menuFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                  horizontalAlignment: Text.AlignRight
                  width: visible ? Math.min(Style.space(300), Math.max(Style.space(80), pagerBar.width * 0.28)) : 0
                }
              }

              Text {
                anchors.centerIn: resultsList
                visible: !root.searchRunning && root.searchQuery !== "" && root.visibleResults.length === 0
                textFormat: Text.PlainText
                text: "No results"
                color: root.dim
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.bodySmall
                font.italic: true
              }

              Text {
                anchors.centerIn: resultsList
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