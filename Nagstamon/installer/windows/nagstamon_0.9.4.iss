[Setup]
AppName=nagstamon
AppVerName=nagstamon 0.9.4
DefaultDirName={pf}\nagstamon
DefaultGroupName=nagstamon
AlwaysUsePersonalGroup=false
ShowLanguageDialog=no
SetupIconFile=C:\Dokumente und Einstellungen\Administrator\Desktop\nagstamon_build\Nagstamon\pyinstaller\nagstamon.ico
UsePreviousGroup=false
OutputBaseFilename=nagstamon_0.9.4_setup
UninstallDisplayIcon=
UsePreviousAppDir=false
AppID={{44F7CFFB-4776-4DA4-9930-A07178069517}
UninstallRestartComputer=false
VersionInfoVersion=0.9.4
VersionInfoCopyright=Henri Wahl
VersionInfoProductName=Nagstamon
VersionInfoProductVersion=0.9.4
InternalCompressLevel=max
Compression=lzma
SolidCompression=true
[Icons]
Name: {group}\nagstamon; Filename: {app}\nagstamon.exe; WorkingDir: {app}; IconFilename: {app}\resources\nagstamon.ico; IconIndex: 0
Name: {commonstartup}\nagstamon; Filename: {app}\nagstamon.exe; WorkingDir: {app}; IconFilename: {app}\resources\nagstamon.ico; IconIndex: 0
[Dirs]
Name: {app}\lib
Name: {app}\resources
Name: {app}\share
Name: {app}\etc
[Files]
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\lib\gtk-2.0\2.10.0\engines\libwimp.dll; DestDir: {app}\lib\gtk-2.0\2.10.0\engines
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\lib\gtk-2.0\2.10.0\loaders\libpixbufloader-png.dll; DestDir: {app}\lib\gtk-2.0\2.10.0\loaders
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\lib\pango\1.6.0\modules\pango-basic-win32.dll; DestDir: {app}\lib\pango\1.6.0\modules
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\acknowledge_dialog.glade; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\close.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\close.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\critical.wav; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\downtime_dialog.glade; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\hostdown.wav; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\hosts.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\hosts.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\LICENSE; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagios.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagios.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon.1; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon.ico; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_black.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_black.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_darkred.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_darkred.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_error.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_error.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_green.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_green.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_label.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_label.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_orange.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_orange.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_red.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_red.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_small.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_small.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_yellow.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\nagstamon_yellow.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\recheckall.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\recheckall.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\refresh.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\refresh.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\services.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\services.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\settings.png; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\settings.svg; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\settings_dialog.glade; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\settings_server_dialog.glade; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\resources\warning.wav; DestDir: {app}\resources\
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\share\themes\MS-Windows\gtk-2.0\gtkrc; DestDir: {app}\share\themes\MS-Windows\gtk-2.0
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\share\xml\libglade\glade-2.0.dtd; DestDir: {app}\share\xml\libglade
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\_hashlib.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\_socket.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\_ssl.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\atk.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\bz2.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\cairo._cairo.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\freetype6.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\gobject._gobject.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\gtk._gtk.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\gtk.glade.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\iconv.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\intl.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libatk-1.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libcairo-2.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libexpat-1.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libfontconfig-1.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libgdk_pixbuf-2.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libgdk-win32-2.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libgio-2.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libglade-2.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libglib-2.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libgmodule-2.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libgobject-2.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libgthread-2.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libgtk-win32-2.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libpango-1.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libpangocairo-1.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libpangoft2-1.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libpangowin32-1.0-0.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libpng14-14.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\libxml2.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\lxml.etree.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\lxml.objectify.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\nagstamon.exe; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\pango.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\pangocairo.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\python25.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\pywintypes25.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\select.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\unicodedata.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\win32api.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\win32pipe.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\winsound.pyd; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\zlib1.dll; DestDir: {app}
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\etc\gtk-2.0\gdk-pixbuf.loaders; DestDir: {app}\etc\gtk-2.0
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\etc\gtk-2.0\gtk.immodules; DestDir: {app}\etc\gtk-2.0
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\etc\gtk-2.0\gtkrc; DestDir: {app}\etc\gtk-2.0
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\etc\gtk-2.0\im-multipress.conf; DestDir: {app}\etc\gtk-2.0
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\etc\pango\pango.aliases; DestDir: {app}\etc\pango
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\etc\pango\pango.modules; DestDir: {app}\etc\pango
Source: Nagstamon\pyinstaller\nagstamon\distnagstamon\msvcr71.dll; DestDir: {app}
