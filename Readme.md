# VRCTracker

Automatically keep track of the worlds you visit in VRChat

## Usage

VRCTracker is a little tool which runs in the background from a system tray icon. It will monitor the VRChat logs and maintain a database of the worlds you visit and when you joined and left them[^1].

Easiest way to use it is to put `VRCTracker.exe` in your `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` folder and have it start automatically. You'll either need to run it then to get going or log out and back in.

Finally, you can export your history by right-clicking on the tray icon. You have a choice of three formats to export as; Markdown, Plain Text and JSON. The right click menu is also how you exit the program.

## Technical Details

VRCTracker uses file system events to tell when VRChat starts. When VRChat isn't running, it doesn't do anything else in the background other than what is necessary to keep the tray icon happy.

While VRChat is running it will monitor the log file it creates, which contains the information we need about your whereabouts.

Application data is stored in the `%LOCALAPPDATA%\ticky\VRCTracker\VRCTracker.db` SQLite database - if you need to delete all your history, you can delete this file.

## Building

Better instructions to come, but this is the command to build a distributable Windows exe:

```batch
pyinstaller --name VRCTracker --add-data="resources\*;resources" --icon resources\vrctracker.ico --onefile --windowed --manifest resources/vrctracker.exe.manifest --version-file resources/file_version_info.txt vrctracker.py
```

This can also be used via system Python but I don't think that's a good move for general distribution. Maybe it'll become a pypi package one day though, who knows.

---

[^1]: It does not keep track of specific instance information (who started it, IDs, regions), just the worlds themselves.