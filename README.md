# Apkedite

A dual-platform APK resource editor.

## Product direction
- Desktop: inspect APK archives, edit text/XML resources, rebuild authorized APKs with Apktool, install/launch them on an Android emulator/device with ADB, and capture screenshots for visual verification.
- Android: inspect APK archives on-device, search entries, edit text/XML resources, and export a portable JSON patch project. Image rendering and full APK rebuilding are follow-up milestones.

Only edit APKs you own or are authorized to modify. No process-memory editing, injection, security bypasses, or tampering with another running app's private data.

## Desktop setup
- Python 3.10+
- pip install -r desktop/requirements.txt
- Optional rebuild: install Apktool and add apktool to PATH.
- Optional live preview: install Android SDK Platform Tools (adb), then connect an emulator or authorized test device.
- Run: python desktop/main.py

## Android setup
Open android/ in Android Studio and build the app module.

## Milestone 0.1
Initial scaffold. Desktop supports archive browsing, text/XML edits, Apktool rebuild integration, and ADB install/launch/screenshot actions. Android supports on-device archive browsing and text/XML editing; patch export and richer image/layout preview are follow-up milestones.
