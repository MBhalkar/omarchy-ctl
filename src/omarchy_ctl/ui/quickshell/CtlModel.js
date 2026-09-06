// Model for CTL bar widget. Runs `omarchy-ctl` commands and exposes results
// to QML. All shelling-out is kept in JS so the QML stays declarative.

var searchResults = []
var searchTotal = 0
var searchQuery = ""
var searchRunning = false
var allTags = []
var tagsRunning = false

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
