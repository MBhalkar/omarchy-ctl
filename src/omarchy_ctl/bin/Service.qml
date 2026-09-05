import QtQuick
import QtQuick.Controls

Item {
    id: root
    property string omarchyPath
    property var shell
    property var manifest
    property var barWidgetRegistry
    property var pluginRegistry

    Component.onCompleted: {
        console.log("mbhalkar.ctl service loaded")
    }
}
