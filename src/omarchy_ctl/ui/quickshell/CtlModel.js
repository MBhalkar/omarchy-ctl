import QtQuick
import Quickshell.Io

// Model for CTL bar widget. Runs `omarchy-ctl` commands and exposes results
// to QML. All shelling-out is kept in JS so the QML stays declarative.

QtObject {
  id: root

  // ---- search ----
  property var searchResults: []
  property int searchTotal: 0
  property string searchQuery: ""
  property bool searchRunning: false

  function runSearch(query) {
    if (!query || query.trim().length === 0) return
    root.searchQuery = query.trim()
    root.searchRunning = true
    root.searchResults = []
    root.searchTotal = 0

    var proc = Qt.createQmlObject('import QtQuick; import Quickshell.Io; Process { property var owner: null }', root, "ctlSearchProc")
    proc.command = ["omarchy-ctl", "search", root.searchQuery, "--json"]
    proc.stdout = StdioCollector {
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
          proc.destroy()
        }
      }
    }
    proc.running = true
  }

  // ---- tags ----
  property var allTags: []
  property bool tagsRunning: false

  function loadTags() {
    if (root.tagsRunning) return
    root.tagsRunning = true
    root.allTags = []

    var proc = Qt.createQmlObject('import QtQuick; import Quickshell.Io; Process { property var owner: null }', root, "ctlTagsProc")
    proc.command = ["omarchy-ctl", "tags", "--json"]
    proc.stdout = StdioCollector {
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
          proc.destroy()
        }
      }
    }
    proc.running = true
  }

  // ---- helpers ----
  function tagColor(tagName) {
    if (!tagName) return Color.foreground
    var hash = 0
    for (var i = 0; i < tagName.length; i++) {
      hash = tagName.charCodeAt(i) + ((hash << 5) - hash)
    }
    var hue = Math.abs(hash % 360)
    return Qt.hsla(hue / 360.0, 0.55, 0.55, 1.0)
  }

  function openFile(path) {
    if (!path) return
    Qt.openUrlExternally(path)
  }
}
