import QtQuick 2.15
import QtQuick.Controls 2.15

Dialog {
    modal: true
    title: "Settings"
    standardButtons: Dialog.Ok

    Label {
        text: "Settings migration is in progress.\nClassic QWidget dialog is used as fallback."
    }
}
