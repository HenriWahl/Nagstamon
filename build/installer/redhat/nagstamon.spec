%define python_sitelib %(%{__python} -c 'from distutils import sysconfig; print sysconfig.get_python_lib()')
%define python_sitearch %(%{__python} -c 'from distutils import sysconfig; print sysconfig.get_python_lib(1)')

Summary: Nagios status monitor for your desktop
Name: nagstamon
Version: 1.0rc2
Release: 1.nagstamon%{?dist}
License: GPL
Group: Applications/Utilities
URL: https://nagstamon.ifw-dresden.de/

Source: http://downloads.sourceforge.net/project/nagstamon/nagstamon/nagstamon%20%{version}/nagstamon_%{version}.tar.gz
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
* Tue Jul 08 2014 Henri Wahl <h.wahl@ifw-dresden.de> - 1.0rc2
- Release candidate 2

* Thu Jun 26 2014 Henri Wahl <h.wahl@ifw-dresden.de> - 1.0rc1
- Release candidate 1.
- mixed in some lines from https://apps.fedoraproject.org/packages/nagstamon/sources/spec/

* Sun Mar 03 2014 Vorontsov Igor <mizunokazumi@mail.ru> - 0.9.12-1.mizu
- Initial package.

