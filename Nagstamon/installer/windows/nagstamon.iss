[Setup]
AppName=Nagstamon
AppVerName=Nagstamon 0.9.6 beta4
DefaultDirName={pf}\Nagstamon
DefaultGroupName=Nagstamon
AlwaysUsePersonalGroup=false
ShowLanguageDialog=no
SetupIconFile=C:\Dokumente und Einstellungen\Administrator\Desktop\svn\trunk\Nagstamon\Nagstamon\resources\nagstamon.ico
UsePreviousGroup=false
OutputBaseFilename=Nagstamon_0.9.6-beta4_setup
UninstallDisplayIcon=
UsePreviousAppDir=false
AppID={{44F7CFFB-4776-4DA4-9930-A07178069517}
UninstallRestartComputer=false
VersionInfoVersion=0.9.6
VersionInfoCopyright=Henri Wahl
VersionInfoProductName=Nagstamon
VersionInfoProductVersion=0.9.6
InternalCompressLevel=max
Compression=lzma
SolidCompression=true
[Icons]
Name: {group}\Nagstamon; Filename: {app}\nagstamon.exe; WorkingDir: {app}; IconFilename: {app}\resources\nagstamon.ico; IconIndex: 0
Name: {commonstartup}\Nagstamon; Filename: {app}\nagstamon.exe; WorkingDir: {app}; IconFilename: {app}\resources\nagstamon.ico; IconIndex: 0
[Files]
Source: ..\..\..\..\dist\nagstamon\atk.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\bz2.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\cairo._cairo.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\freetype6.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\gobject._gobject.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\gtk._gtk.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\iconv.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\intl.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libatk-1.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libcairo-2.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libexpat-1.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libfontconfig-1.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libgdk_pixbuf-2.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libgdk-win32-2.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libgio-2.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libglib-2.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libgmodule-2.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libgobject-2.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libgthread-2.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libgtk-win32-2.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libpango-1.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libpangocairo-1.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libpangoft2-1.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libpangowin32-1.0-0.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libpng14-14.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\libxml2.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\lxml.etree.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\lxml.objectify.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\MSVCR71.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\nagstamon.exe; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\pango.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\pangocairo.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\pyexpat.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\python25.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\pywintypes25.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\select.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\unicodedata.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\win32api.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\win32pipe.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\winsound.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\zlib1.dll; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\resources\acknowledge_dialog.ui; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\close.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\close.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\critical.wav; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\downtime_dialog.ui; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\hostdown.wav; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\hosts.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\hosts.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\LICENSE; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagios.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagios.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon.1; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon.icns; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon.ico; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_black.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_black.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_darkred.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_darkred.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_error.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_error.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_acknowledged.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_acknowledged.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_downtime.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_downtime.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_green.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_green.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_label.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_label.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_orange.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_orange.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_red.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_red.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_small.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_small.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_yellow.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\nagstamon_yellow.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\recheckall.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\recheckall.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\refresh.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\refresh.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\services.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\services.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\settings.png; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\settings.svg; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\settings_dialog.ui; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\settings_server_dialog.ui; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\resources\warning.wav; DestDir: {app}\resources\
Source: ..\..\..\..\dist\nagstamon\etc\gtk-2.0\gdk-pixbuf.loaders; DestDir: {app}\etc\gtk-2.0
Source: ..\..\..\..\dist\nagstamon\etc\gtk-2.0\gtk.immodules; DestDir: {app}\etc\gtk-2.0
Source: ..\..\..\..\dist\nagstamon\etc\gtk-2.0\gtkrc; DestDir: {app}\etc\gtk-2.0
Source: ..\..\..\..\dist\nagstamon\etc\gtk-2.0\im-multipress.conf; DestDir: {app}\etc\gtk-2.0
Source: ..\..\..\..\dist\nagstamon\etc\pango\pango.aliases; DestDir: {app}\etc\pango
Source: ..\..\..\..\dist\nagstamon\etc\pango\pango.modules; DestDir: {app}\etc\pango
Source: ..\..\..\..\dist\nagstamon\lib\gtk-2.0\2.10.0\engines\libwimp.dll; DestDir: {app}\lib\gtk-2.0\2.10.0\engines
Source: ..\..\..\..\dist\nagstamon\lib\gtk-2.0\2.10.0\loaders\libpixbufloader-png.dll; DestDir: {app}\lib\gtk-2.0\2.10.0\loaders
Source: ..\..\..\..\dist\nagstamon\lib\pango\1.6.0\modules\pango-basic-win32.dll; DestDir: {app}\lib\pango\1.6.0\modules
Source: ..\..\..\..\dist\nagstamon\share\themes\MS-Windows\gtk-2.0\gtkrc; DestDir: {app}\share\themes\MS-Windows\gtk-2.0
Source: ..\..\..\..\dist\nagstamon\_hashlib.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\_socket.pyd; DestDir: {app}
Source: ..\..\..\..\dist\nagstamon\_ssl.pyd; DestDir: {app}
[Dirs]
Name: {app}\resources
Name: {app}\etc
Name: {app}\lib
Name: {app}\share
