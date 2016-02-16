%define python_sitelib %(%{__python} -c 'from distutils import sysconfig; print sysconfig.get_python_lib()')
%define python_sitearch %(%{__python} -c 'from distutils import sysconfig; print sysconfig.get_python_lib(1)')

Summary: Nagios status monitor for your desktop
Name: nagstamon
Version: 1.0.1
Release: 1.nagstamon%{?dist}
License: GPL
Group: Applications/Utilities
URL: https://nagstamon.ifw-dresden.de/

Source: http://nagstamon.ifw-dresden.de/files-nagstamon/stable/Nagstamon-%{version}.tar.gz
Source1: nagstamon.desktop
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

Buildarch: noarch
BuildRequires: desktop-file-utils
BuildRequires: Distutils
Requires: gnome-icon-theme
Requires: pygtk2
Requires: python >= 2.7
Requires: python-setuptools
Requires: python-keyring
Requires: python-SecretStorage
Requires: python-crypto
Requires: python-BeautifulSoup
Requires: sox


%description
Nagstamon is a Nagios status monitor for the desktop. It connects to multiple
Nagios, Icinga, Opsview, Centreon, Op5 Monitor/Ninja and Check_MK Multisite
monitoring servers and resides in systray or as a floating statusbar at the
desktop showing a brief summary of critical, warning, unknown, unreachable and
down hosts and services and pops up a detailed status overview when moving the
mouse pointer over it. Connecting to displayed hosts and services is easily
established by context menu via SSH, RDP and VNC. Users can be notified by
sound. Hosts and services can be filtered by category and regular expressions.

%prep
%setup -n Nagstamon

#Remove embedded BeautifulSoup http://sourceforge.net/p/nagstamon/bugs/44/
rm -rf Nagstamon/thirdparty/BeautifulSoup.py

%build
cd ../
%{__python} setup.py build

%install
cd ../
%{__rm} -rf %{buildroot}
%{__python} setup.py install --skip-build --root="%{buildroot}" --prefix="%{_prefix}"

%{__chmod} +x %{buildroot}%{python_sitelib}/Nagstamon/Server/Multisite.py

#Provide directory to install icon for desktop file
mkdir -p %{buildroot}%{_datadir}/pixmaps

#Copy icon to pixmaps directory
cp Nagstamon/resources/%{name}.svg %{buildroot}%{_datadir}/pixmaps/%{name}.svg

#Remove execute bit from icon
chmod -x %{buildroot}%{_datadir}/pixmaps/%{name}.svg

#Remove the file extension for convenience
mv %{buildroot}%{_bindir}/%{name}.py %{buildroot}%{_bindir}/%{name}

# install the desktop file
desktop-file-install --dir %{buildroot}/%{_datadir}/applications\
                     --delete-original\
                     --set-icon=%{name}.svg\
                     %{buildroot}%{python_sitelib}/Nagstamon/resources/%{name}.desktop

# fix for stupid strip issue
#%{__chmod} -R u+w %{buildroot}/*

%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-, root, root, 0755)
#%doc COPYRIGHT ChangeLog LICENSE
%doc %{_mandir}/man?/*
%{_bindir}/%{name}
%{_datadir}/pixmaps/*
%{_datadir}/applications/%{name}.desktop
%{python_sitelib}/Nagstamon
%{python_sitelib}/nagstamon-*-py*.egg-info

%changelog
* Mon Sep 22 2014 Henri Wahl <h.wahl@ifw-dresden.de> - 1.0.1
- added option to disable system keyring storage to prevent crashes
- fixed too narrow fullscreen display
- reverted default sorting order to "Descending"
- fixed vanishing Nagstamon submenu in Ubuntu Appindicator

* Tue Jul 28 2014 Henri Wahl <h.wahl@ifw-dresden.de> - 1.0
- added custom event notification with custom commands
- added highlighting of new events
- added storage of passwords in OS keyring
- added optional tooltip for full status information
- added support for applying custom actions to specific monitor only
- added copy buttons for servers and actions dialogs
- added stopping notification if event already vanished
- added support for Op5Monitor 6.3 instead of Ninja
- added experimental Zabbix support
- added automatic refreshing after acknowledging
- added permanent hamburger menu
- unified layout of dialogs
- various Check_MK improvements
- fixed old regression not-staying-on-top-bug
- fixed Check_MK-Recheck-DOS-bug
- fixed pop window size calculation on multiple screens
- fixed following popup window on multiple screens
- fixed hiding dialogs in MacOSX
- fixed ugly statusbar font in MacOSX
- fixed use of changed colors
- fixed non-ascending default sort order
- fixed Opsview downtime dialog
- fixed sometimes not working context menu
- fixed some GUI glitches
- fixed password saving bug
- fixed Centreon language inconsistencies
- fixed regression Umlaut bug

* Tue Jul 08 2014 Henri Wahl <h.wahl@ifw-dresden.de> - 1.0rc2
- Release candidate 2

* Thu Jun 26 2014 Henri Wahl <h.wahl@ifw-dresden.de> - 1.0rc1
- Release candidate 1.
- mixed in some lines from https://apps.fedoraproject.org/packages/nagstamon/sources/spec/

* Sun Mar 03 2014 Vorontsov Igor <mizunokazumi@mail.ru> - 0.9.12-1.mizu
- Initial package.

