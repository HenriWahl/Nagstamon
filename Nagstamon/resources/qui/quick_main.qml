import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: root
    width: 760
    height: 520
    minimumWidth: 520
    minimumHeight: 360
    visible: false
    title: "Nagstamon"

    header: ToolBar {
        contentItem: RowLayout {
            spacing: 8

            Label {
                text: "Nagstamon"
                font.bold: true
                Layout.fillWidth: true
            }

            Button {
                text: "Recheck"
                onClicked: nagstamonBridge.trigger_recheck()
            }
            Button {
                text: "Settings"
                onClicked: nagstamonBridge.open_settings()
            }
            Button {
                text: "About"
                onClicked: nagstamonBridge.open_about()
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        Frame {
            Layout.fillWidth: true

            RowLayout {
                anchors.fill: parent
                spacing: 10

                Label { text: "Critical: " + nagstamonBridge.criticalCount }
                Label { text: "Warning: " + nagstamonBridge.warningCount }
                Label { text: "Unknown: " + nagstamonBridge.unknownCount }
                Label { text: "Unreachable: " + nagstamonBridge.unreachableCount }
                Label { text: "Down: " + nagstamonBridge.downCount }
            }
        }

        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: serverList
                model: nagstamonBridge.serverNames
                implicitWidth: 230
                clip: true

                delegate: Rectangle {
                    required property string modelData
                    required property int index
                    width: serverList.width
                    height: 34
                    color: ListView.isCurrentItem ? "#263545" : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        color: ListView.isCurrentItem ? "white" : palette.text
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            serverList.currentIndex = index
                            nagstamonBridge.select_server(modelData)
                        }
                    }
                }
            }

            Frame {
                SplitView.fillWidth: true
                SplitView.fillHeight: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    Label {
                        text: nagstamonBridge.selectedServer === "" ? "No server selected" : "Server: " + nagstamonBridge.selectedServer
                        font.bold: true
                    }

                    RowLayout {
                        spacing: 8
                        Button { text: "Acknowledge"; onClicked: nagstamonBridge.acknowledge() }
                        Button { text: "Downtime"; onClicked: nagstamonBridge.downtime() }
                        Button { text: "Submit"; onClicked: nagstamonBridge.submit_check_result() }
                        Button { text: "Web"; onClicked: nagstamonBridge.web_login() }
                    }

                    Label {
                        text: "QtQuick compatibility mode: QWidget dialogs are still used while QML slices are migrated."
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }
        }
    }
}
