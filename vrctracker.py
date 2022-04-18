#!/usr/bin/env python

import os
import time
import logging
import sqlite3
import sys
import re

from appdirs import AppDirs
from datetime import datetime
from dateutil.parser import parse as parse_date
from dateutil.utils import default_tzinfo
from dateutil.tz import gettz
from PIL import Image
import psutil
import pystray
from threading import Thread, Event as ThreadingEvent
from tkinter import filedialog, messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

APP_EMBEDDED = getattr(sys, "frozen", False)

DB_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS worlds (
    id TEXT NOT NULL PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS checkins (
    world_id TEXT NOT NULL,
    start_datetime TEXT NOT NULL,
    end_datetime TEXT,
    FOREIGN KEY(world_id) REFERENCES worlds(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX checkins_world_id_time_unique ON checkins(world_id, start_datetime); 

CREATE TABLE IF NOT EXISTS visitors (
    world_id TEXT NOT NULL,
    name TEXT NOT NULL,
    start_datetime TEXT NOT NULL,
    end_datetime TEXT,
    FOREIGN KEY(world_id) REFERENCES worlds(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX visitors_world_id_name_time_unique ON visitors(world_id, name, start_datetime); 
"""

EXPORT_FILETYPES = [("Markdown", ".md"), ("Plain Text", ".txt"), ("JSON Data", ".json")]


class FileCreatedEventHandler(FileSystemEventHandler):
    def __init__(self, app, logger=None):
        super().__init__()

        self.app = app
        self.logger = logger or logging.root

    def on_created(self, event):
        super().on_created(event)

        if event.is_directory:
            return

        relpath = os.path.relpath(event.src_path, self.app.vrchat_data_dir)

        if not relpath.startswith("output_log"):
            return

        self.logger.info("VRChat log file detected: %s", relpath)

        vrchat_process = None
        for process in psutil.process_iter(["name"]):
            if process.info["name"] == "VRChat.exe":
                vrchat_process = process
                break

        self.logger.info("VRChat process detected: %d", vrchat_process.pid)

        Thread(
            target=self.app.follow_log_file, args=(event.src_path, vrchat_process)
        ).start()


VRCHAT_DIR = "%LOCALAPPDATA%\\..\\LocalLow\\VRChat\\VRChat"


class VRCTrackerApp:
    def get_user_data_dir():
        user_data_dir = AppDirs("VRCTracker", "ticky").user_data_dir
        if not os.path.isdir(user_data_dir):
            os.makedirs(user_data_dir, exist_ok=True)
        return user_data_dir

    def get_vrchat_data_dir():
        expanded_dir = os.path.expandvars(VRCHAT_DIR)

        # Fallback for non-windows systems
        if expanded_dir == VRCHAT_DIR:
            return AppDirs("VRChat", "VRChat").user_data_dir

        return os.path.abspath(expanded_dir)

    def __init__(
        self,
        user_data_dir=get_user_data_dir(),
        vrchat_data_dir=get_vrchat_data_dir(),
        database_path=None,
        logger=None,
    ):
        self.logger = logger or logging.root

        self.logger.debug("user_data_dir: %s", user_data_dir)

        self.vrchat_data_dir = vrchat_data_dir

        self.logger.debug("vrchat_data_dir: %s", self.vrchat_data_dir)

        if not os.path.exists(self.vrchat_data_dir):
            print("{} could not be found".format(self.vrchat_data_dir))
            return

        if database_path is None:
            self.database_path = os.path.join(user_data_dir, "VRCTracker.db")
        else:
            self.database_path = database_path

        self.logger.debug("database_path: %s", self.database_path)
        db_conn = sqlite3.connect(self.database_path)

        db = db_conn.cursor()
        db_check = db.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='checkins';"
        ).fetchone()
        if db_check[0] == 0:
            self.logger.info("initialising database...")
            db.executescript(DB_SCHEMA)
            db_conn.commit()
            self.logger.info("database ready")

        if APP_EMBEDDED:
            iconimage = Image.open(
                os.path.join(sys._MEIPASS, "resources/vrctracker.ico")
            )
        else:
            iconimage = Image.open("resources/vrctracker.ico")

        self.icon = pystray.Icon(
            "VRCTracker",
            icon=iconimage,
            title="VRCTracker",
            menu=pystray.Menu(
                pystray.MenuItem("Export Location History...", self.on_export),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", self.on_exit),
            ),
        )

    def format_as(self, extension, output_file):
        db_conn = sqlite3.connect(self.database_path)
        db = db_conn.cursor()

        # TODO: Gracefully handle errors fetching from database
        if extension == ".md":
            result = db.execute(
                """
                SELECT '- [' || ifnull(worlds.name, worlds.id) || '](https://vrch.at/' || worlds.id || ')  \n  from ' || ifnull(STRFTIME('%d/%m/%Y, %H:%M', checkins.start_datetime), '(unknown)') || ' until ' || ifnull(STRFTIME('%d/%m/%Y, %H:%M', checkins.end_datetime), '(unknown)')
                FROM checkins
                INNER JOIN worlds
                ON checkins.world_id = worlds.id
            """
            ).fetchall()

            self.logger.info("History: {}".format(result))

            output_file.write("# VRCTracker Location History\n\n")
            output_file.writelines("{}\n".format(row[0]) for row in result)

        elif extension == ".txt":
            result = db.execute(
                """
                SELECT ifnull(worlds.name, worlds.id) || ' (https://vrch.at/' || worlds.id || '), from ' || ifnull(STRFTIME('%d/%m/%Y, %H:%M', checkins.start_datetime), '(unknown)') || ' until ' || ifnull(STRFTIME('%d/%m/%Y, %H:%M', checkins.end_datetime), '(unknown)')
                FROM checkins
                INNER JOIN worlds
                ON checkins.world_id = worlds.id
            """
            ).fetchall()

            self.logger.info("History: {}".format(result))

            output_file.writelines("{}\n".format(row[0]) for row in result)

        elif extension == ".json":
            result = db.execute(
                """
                SELECT json_group_array(json_object(
                    'world_name', worlds.name, 
                    'world_url', 'https://vrch.at/' || worlds.id,
                    'start_datetime', checkins.start_datetime,
                    'end_datetime', checkins.end_datetime 
                ))
                FROM checkins
                INNER JOIN worlds
                ON checkins.world_id = worlds.id
            """
            ).fetchone()

            output_file.write(result[0])
        else:
            raise NotImplementedError("Unexpected file extension: {}".format(extension))

        db_conn.commit()

    def on_export(self, icon, item):
        outfilename = filedialog.asksaveasfilename(
            title="Save VRChat Location History",
            initialfile="VRCTracker History",
            filetypes=EXPORT_FILETYPES,
            defaultextension=EXPORT_FILETYPES,
        )

        (_, extension) = os.path.splitext(outfilename)

        self.logger.info(
            "Saving location history as %s, with format %s", outfilename, extension
        )

        with open(outfilename, mode="w", encoding="utf-8") as output_file:
            try:
                self.format_as(extension, output_file)
            except Exception as e:
                messagebox.showerror(
                    title="VRCTracker",
                    message=str(e),
                )

    def on_exit(self, icon, item):
        self.stop_event.set()
        icon.stop()

    def run(self):
        self.stop_event = ThreadingEvent()
        self.icon.run(setup=self.pystray_setup)

    def pystray_setup(self, icon):
        icon.visible = True

        event_handler = FileCreatedEventHandler(self, self.logger)
        observer = Observer()
        observer.schedule(event_handler, self.vrchat_data_dir)
        observer.start()

        try:
            while True:
                if self.stop_event.is_set():
                    observer.stop()
                    break

                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()

        observer.join()

    def follow_log_file(self, path, responsible_process):
        # https://medium.com/@aliasav/how-follow-a-file-in-python-tail-f-in-python-bca026a901cf
        with open(path, mode="r", encoding="utf-8", errors="ignore") as input_file:
            db_conn = sqlite3.Connection(self.database_path)
            db = db_conn.cursor()
            world_id = None

            while not self.stop_event.is_set():
                line = input_file.readline()

                if not line:
                    if (
                        responsible_process == None
                        or not responsible_process.is_running()
                    ):
                        break

                    time.sleep(0.1)
                    continue

                last_world_id = world_id

                # Regexes inspired by https://github.com/sunasaji/VRC_log_checker

                # Gather world IDs from Joining messages
                match = re.search(
                    "([0-9\.]+ [0-9:]+).+Joining (wrld_[0-9a-f\-]{36})", line
                )
                if match != None:
                    date = default_tzinfo(parse_date(match.group(1)), gettz())
                    world_id = match.group(2)

                    self.logger.info(
                        "Entered world %s at %s", world_id, date.isoformat()
                    )

                    # Update any unresolved checkins to the previous world to have ended
                    db.execute(
                        "UPDATE checkins SET end_datetime = :end_datetime WHERE world_id = :last_world_id AND end_datetime IS NULL",
                        {
                            "end_datetime": date.isoformat(),
                            "last_world_id": last_world_id,
                        },
                    )
                    # Insert a world ID value, but ignore if there's a conflict
                    db.execute(
                        "INSERT OR IGNORE INTO worlds (id) VALUES (:id)",
                        {"id": world_id},
                    )
                    # Insert a fresh checkin beginning at this time
                    db.execute(
                        "INSERT INTO checkins (world_id, start_datetime) VALUES (:world_id, :start_datetime)",
                        {"world_id": world_id, "start_datetime": date.isoformat()},
                    )
                    db_conn.commit()

                # Gather world names from Joining messages
                match = re.search(
                    "[0-9\.]+ [0-9:]+.+Joining or Creating Room: (.+)", line
                )
                if match != None:
                    name = match.group(1)
                    self.logger.info('Found world name: "%s"', name)
                    db.execute(
                        "UPDATE worlds SET name = :name WHERE id = :id",
                        {"name": name, "id": world_id},
                    )
                    db_conn.commit()

                # Gather player names from OnPlayerJoined/Left events
                match = re.search("([0-9\.]+ [0-9:]+).+OnPlayerJoined (.+)", line)
                if match != None:
                    date = default_tzinfo(parse_date(match.group(1)), gettz())
                    self.logger.info(
                        'Player "%s" Joined, at %s', match.group(2), date.isoformat()
                    )

                match = re.search("([0-9\.]+ [0-9:]+).+OnPlayerLeft (.+)", line)
                if match != None:
                    date = default_tzinfo(parse_date(match.group(1)), gettz())
                    self.logger.info(
                        'Player "%s" Left, at %s', match.group(2), date.isoformat()
                    )

            # Update any unresolved checkins to the previous world to have ended
            db.execute(
                "UPDATE checkins SET end_datetime = :end_datetime WHERE world_id = :world_id AND end_datetime IS NULL",
                {
                    "end_datetime": default_tzinfo(datetime.now(), gettz()).isoformat(),
                    "world_id": world_id,
                },
            )
            db_conn.commit()

            self.logger.info("Stopped processing %s", path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    app = VRCTrackerApp()
    app.run()
