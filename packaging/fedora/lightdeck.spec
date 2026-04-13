Name:           lightdeck
Version:        1.0.0
Release:        1%{?dist}
Summary:        System monitoring & LED control for Linux
License:        PolyForm-Noncommercial-1.0.0
URL:            https://github.com/Dirt-Ronin/lightdeck
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python3
Requires:       python3-pyqt6
Requires:       python3-psutil
Recommends:     openrgb
Recommends:     lm_sensors

%description
LightDeck is a system monitoring and RGB LED control application for Linux.
Real-time hardware gauges, Grafana-style sparkline graphs, gaming overlay,
desktop widgets, and LED effect presets from 12 ecosystems.

Zero telemetry. Full sarcasm.

%prep
%autosetup -n %{name}-%{version}

%install
install -d %{buildroot}%{_datadir}/%{name}
cp -r *.py drivers/ %{buildroot}%{_datadir}/%{name}/
install -Dm644 icon.svg %{buildroot}%{_datadir}/%{name}/icon.svg

# Launcher
install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/%{name} << 'EOF'
#!/bin/bash
exec python3 %{_datadir}/%{name}/main.py "$@"
EOF
chmod 755 %{buildroot}%{_bindir}/%{name}

# Desktop entry
install -Dm644 /dev/stdin %{buildroot}%{_datadir}/applications/%{name}.desktop << 'EOF'
[Desktop Entry]
Name=LightDeck
Comment=System monitoring & LED control
Exec=lightdeck
Icon=lightdeck
Terminal=false
Type=Application
Categories=Utility;System;
EOF

# Icon
install -Dm644 icon.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

# License
install -Dm644 LICENSE %{buildroot}%{_datadir}/licenses/%{name}/LICENSE

%files
%license LICENSE
%{_bindir}/%{name}
%{_datadir}/%{name}/
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

%changelog
* Sun Apr 13 2026 Dirt-Ronin <dirtronin@outlook.com> - 1.0.0-1
- Initial release
