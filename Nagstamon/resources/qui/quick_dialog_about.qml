import QtQuick 2.15
import QtQuick.Controls 2.15

Dialog {
    modal: true
    title: "About"
    standardButtons: Dialog.Ok

    Label {
        text: "QtQuick frontend is active.\nLegacy About dialog remains available for fallback."
    }
}
