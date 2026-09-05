import QtQuick
import QtQuick.Controls
import Omarchy

Item {
    id: root
    property string omarchyPath
    property var shell
    property var manifest
    property var barWidgetRegistry
    property var pluginRegistry

    Component.onCompleted: {
        console.log("omarchy.ctl service loaded")
    }
}
