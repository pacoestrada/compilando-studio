Name:           compilando-studio
Version:        0.1.2
Release:        1
Summary:        Editor de podcast Compilando Studio
License:        GPL-3.0-or-later
URL:            https://github.com/pacoestrada/compilando-studio
Source0:        %{name}-%{version}-source.tar.gz
BuildArch:      noarch
AutoReqProv:    no
Requires:       python3 >= 3.10
Requires:       python3-numpy
Requires:       python3-qt5
Requires:       qt5-qtmultimedia
Requires:       /usr/bin/python3
Requires:       /usr/bin/ffmpeg
Requires:       /usr/bin/ffprobe
Recommends:     audacity

# Pure Python kept as source: no host-specific bytecode or native binaries.
%global __os_install_post %{nil}

%description
Edicion no destructiva de voz y musica, cortes automaticos y fundidos,
vúmetro digital y exportacion MP3, WAV y FLAC. Primera version en desarrollo.
El exportador MP3 necesita FFmpeg con el codificador libmp3lame.

%prep
%setup -q -n %{name}-%{version}

%build

%install
mkdir -p %{buildroot}/usr/share/compilando-studio
cp -a compilando assets docs README.md LICENSE %{buildroot}/usr/share/compilando-studio/
mkdir -p %{buildroot}/usr/bin %{buildroot}/usr/share/applications
cat > %{buildroot}/usr/bin/compilando-studio <<'LAUNCHER'
#!/bin/sh
export PYTHONPATH=/usr/share/compilando-studio${PYTHONPATH:+:$PYTHONPATH}
exec /usr/bin/python3 -B -m compilando "$@"
LAUNCHER
chmod 755 %{buildroot}/usr/bin/compilando-studio
cat > %{buildroot}/usr/share/applications/compilando-studio.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Compilando Studio
Comment=Edición y mezcla de podcast con estilo de radio
Exec=compilando-studio %%f
Icon=/usr/share/compilando-studio/assets/logo.jpg
Terminal=false
Categories=AudioVideo;Audio;AudioVideoEditing;
MimeType=audio/x-wav;audio/wav;audio/flac;audio/x-flac;audio/mpeg;
StartupNotify=true
DESKTOP

%files
%defattr(-,root,root,-)
/usr/bin/compilando-studio
/usr/share/applications/compilando-studio.desktop
/usr/share/compilando-studio

%changelog
* Tue Nov 10 2026 Compilando Podcast - 0.1.2-1
- Primer paquete RPM; mismo codigo de aplicacion que la etiqueta v0.1.2.
