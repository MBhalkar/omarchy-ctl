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

function pageSizeOptions(total) {
  if (!total || total <= 0) return [{ label: "50", value: "50" }]
  var opts = []
  var candidates = [10, 25, 50, 100, 250, 500]
  for (var i = 0; i < candidates.length; i++) {
    if (candidates[i] < total) opts.push({ label: String(candidates[i]), value: String(candidates[i]) })
  }
  opts.push({ label: "All (" + total + ")", value: String(total) })
  return opts
}

function preferredPageSize(total) {
  if (!total || total <= 0) return 50
  if (total < 25) return total
  if (total <= 50) return 25
  return 50
}

function sanitizeName(name) {
  if (!name) return "all"
  return name.replace(/[^a-zA-Z0-9_.-]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40) || "all"
}
