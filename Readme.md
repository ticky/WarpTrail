# WarpTrail for VRChat

[![Python](https://github.com/ticky/WarpTrail/actions/workflows/python.yml/badge.svg)](https://github.com/ticky/WarpTrail/actions/workflows/python.yml)

Automatically keep track of the worlds you visit in VRChat

## Usage

WarpTrail is a little tool which runs in the background from a system tray icon. It will monitor the VRChat logs and maintain a database of the worlds you visit and when you joined and left them[^1].

Easiest way to use it is to put `WarpTrail.exe` in your `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` folder and have it start automatically. You'll either need to run it then to get going or log out and back in.

Finally, you can export your history by right-clicking on the tray icon. You have a choice of three formats to export as; Markdown, Plain Text and JSON. The right click menu is also how you exit the program.

## Technical Details

WarpTrail uses file system events to tell when VRChat starts. When VRChat isn't running, it doesn't do anything else in the background other than what is necessary to keep the tray icon happy.

While VRChat is running it will monitor the log file it creates, which contains the information we need about your whereabouts.

Application data is stored in the `%LOCALAPPDATA%\ticky\WarpTrail\WarpTrail.db` SQLite database - if you need to delete all your history, you can delete this file.

## Building

Better instructions to come, but this is the command to build a distributable Windows exe:

```batch
pyinstaller --name WarpTrail --add-data="resources\*;resources" --icon resources\warptrail.ico --onefile --windowed --manifest resources/warptrail.exe.manifest --version-file resources/file_version_info.txt warptrail.py
```

This can also be used via system Python but I don't think that's a good move for general distribution. Maybe it'll become a pypi package one day though, who knows.

## Testing

A test suite is included, and automatically executed by GitHub Actions.

Tests can be executed using either:

```shell
python3 test_warptrail.py
```

or, if pytest is installed:

```shell
pytest
```

---

[^1]: It does not keep track of specific instance information (who started it, IDs, regions), just the worlds themselves.