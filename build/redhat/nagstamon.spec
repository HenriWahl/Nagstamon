%global gitdate 20160602
%global commit 7139844d1a8109ba45f03601293ab70050b7dc94
%global shortcommit %(c=%{commit}; echo ${c:0:7})

Name:     nagstamon
Version:  2.0
Release:  0.1.%{gitdate}git%{shortcommit}%{?dist}
Summary:  Nagios status monitor for desktop

License:  GPLv2+
URL:      https://nagstamon.ifw-dresden.de
Source0:  https://github.com/HenriWahl/Nagstamon/archive/%{commit}/nagstamon-%{commit}.tar.gz

BuildArch:     noarch
BuildRequires: python3-devel
BuildRequires: python3-qt5-devel
BuildRequires: desktop-file-utils
Requires:      python3
Requires:      python3-qt5
Requires:      python3-beautifulsoup4
Requires:      python3-requests
Requires:      python3-qt5
Requires:      python3-SecretStorage
Requires:      python3-crypto
Requires:      python3-cryptography
Requires:      python3-psutil
Requires:      qt5-qtsvg
Requires:      qt5-qtmultimedia

%description
Nagstamon is a Nagios status monitor which takes place in system tray
or on desktop (GNOME, KDE, Windows) as floating status bar to inform
you in real-time about the status of your Nagios and derivatives
monitored network. It allows to connect to multiple Nagios, Icinga,
Opsview, Op5Monitor, Check_MK/Multisite, Centreon and Thruk servers.

%prep
%setup -qn Nagstamon-%{commit}

%build
%{__python3} setup.py build

%install
%{__python3} setup.py install --single-version-externally-managed -O1 --root=%{buildroot}

#Fix 'non-executable-script' error
chmod +x %{buildroot}%{python3_sitelib}/Nagstamon/Servers/Multisite.py
chmod +x %{buildroot}%{python3_sitelib}/Nagstamon/thirdparty/keyring/cli.py
chmod +x %{buildroot}%{python3_sitelib}/Nagstamon/Config.py

#Provide directory to install icon for desktop file
mkdir -p %{buildroot}%{_datadir}/pixmaps

#Copy icon to pixmaps directory
cp Nagstamon/resources/%{name}.svg %{buildroot}%{_datadir}/pixmaps/%{name}.svg

#Remove execute bit from icon
chmod -x %{buildroot}%{_datadir}/pixmaps/%{name}.svg

#Remove the file extension for convenience
mv %{buildroot}%{_bindir}/%{name}.py %{buildroot}%{_bindir}/%{name}

desktop-file-install --dir %{buildroot}/%{_datadir}/applications\
                     --delete-original\
                     --set-icon=%{name}.svg\
                     %{buildroot}%{python3_sitelib}/Nagstamon/resources/%{name}.desktop

%files
%doc ChangeLog
%license COPYRIGHT LICENSE
%{_datadir}/pixmaps/%{name}.svg
%{_datadir}/applications/%{name}.desktop
%{python3_sitelib}/Nagstamon/
%{_bindir}/%{name}
%{_mandir}/man1/%{name}.1*
%{python3_sitelib}/%{name}*.egg-info

%changelog
* Sun Jun 05 2016 Momcilo Medic <fedorauser@fedoraproject.org> 2.0-0.1.20160602git7139844
- Initial .spec file
