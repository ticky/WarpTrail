#!/usr/bin/env python

import os
import time
import logging
import sqlite3
import re

from appdirs import AppDirs
from datetime import datetime
from dateutil.parser import parse as parse_date
from dateutil.utils import default_tzinfo
from dateutil.tz import gettz
import psutil
import pystray
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

DB_SCHEMA = '''
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
'''

class VRCTrackerApp:
    def __init__(self, logger=None):
        self.logger = logger or logging.root

        user_data_dir = AppDirs("VRCTracker", "ticky").user_data_dir
        if not os.path.isdir(user_data_dir):
            os.makedirs(user_data_dir, exist_ok=True)
        self.logger.debug("user_data_dir: %s", user_data_dir)
    
        self.vrchat_data_dir = os.path.abspath(os.path.expandvars("%LOCALAPPDATA%\..\LocalLow\VRChat\VRChat"))

        self.logger.debug("path: %s", self.vrchat_data_dir)

        if not os.path.exists(self.vrchat_data_dir):
            print('{} could not be found'.format(self.vrchat_data_dir))
            return

        self.database_path = os.path.join(user_data_dir, "VRCTracker.db")
        self.logger.debug("database_path: %s", self.database_path)
        db_conn = sqlite3.connect(self.database_path)

        db = db_conn.cursor()
        db_check = db.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='checkins';").fetchone()
        if db_check[0] == 0:
            self.logger.info("initialising database...")
            db.executescript(DB_SCHEMA)
            db_conn.commit()
            self.logger.info("database ready")
    
    def run(self):
        event_handler = FileCreatedEventHandler(self, self.logger)
        observer = Observer()
        observer.schedule(event_handler, self.vrchat_data_dir)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()

        observer.join()

    def follow_log(self, path, responsible_process):
        # https://medium.com/@aliasav/how-follow-a-file-in-python-tail-f-in-python-bca026a901cf
        with open(path, mode='r', encoding='utf-8', errors='ignore') as input_file:
            db_conn = sqlite3.Connection(self.database_path)
            db = db_conn.cursor()
            world_id = None
            while responsible_process != None and responsible_process.is_running():
                line = input_file.readline()

                if not line:
                    time.sleep(0.1)
                    continue
                
                last_world_id = world_id

                # Regexes inspired by https://github.com/sunasaji/VRC_log_checker

                # Gather world IDs from Joining messages
                match = re.search('([0-9\.]+ [0-9:]+).+Joining (wrld_[0-9a-f\-]{36})', line)
                if match != None:
                    date = default_tzinfo(parse_date(match.group(1)), gettz())
                    world_id = match.group(2)

                    self.logger.info("Entered world %s at %s", world_id, date.isoformat())

                    # Update any unresolved checkins to the previous world to have ended
                    db.execute(
                        "UPDATE checkins SET end_datetime = :end_datetime WHERE world_id = :last_world_id AND end_datetime IS NULL",
                        {"end_datetime": date.isoformat(), "last_world_id": last_world_id}
                    )
                    # Insert a world ID value, but ignore if there's a conflict
                    db.execute(
                        "INSERT OR IGNORE INTO worlds (id) VALUES (:id)",
                        {"id": world_id}
                    )
                    # Insert a fresh checkin beginning at this time
                    db.execute(
                        "INSERT INTO checkins (world_id, start_datetime) VALUES (:world_id, :start_datetime)",
                        {"world_id": world_id, "start_datetime": date.isoformat()}
                    )
                    db_conn.commit()

                # Gather world names from Joining messages
                match = re.search('[0-9\.]+ [0-9:]+.+Joining or Creating Room: (.+)', line)
                if match != None:
                    name = match.group(1)
                    self.logger.info("Found world name: \"%s\"", name)
                    db.execute(
                        "UPDATE worlds SET name = :name WHERE id = :id",
                        {"name": name, "id": world_id}
                    )
                    db_conn.commit()
                
                # Gather player names from OnPlayerJoined/Left events
                match = re.search('([0-9\.]+ [0-9:]+).+OnPlayerJoined (.+)', line)
                if match != None:
                    date = default_tzinfo(parse_date(match.group(1)), gettz())
                    self.logger.info("Player \"%s\" Joined, at %s", match.group(2), date.isoformat())

                match = re.search('([0-9\.]+ [0-9:]+).+OnPlayerLeft (.+)', line)
                if match != None:
                    date = default_tzinfo(parse_date(match.group(1)), gettz())
                    self.logger.info("Player \"%s\" Left, at %s", match.group(2), date.isoformat())
        
            # Update any unresolved checkins to the previous world to have ended
            db.execute(
                "UPDATE checkins SET end_datetime = :end_datetime WHERE world_id = :world_id AND end_datetime IS NULL",
                {"end_datetime": default_tzinfo(datetime.now(), gettz()).isoformat(), "world_id": world_id}
            )
            db_conn.commit()

            self.logger.info("VRChat process exited; done processing %s", path)

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
        for process in psutil.process_iter(['name']):
            if process.info['name'] == "VRChat.exe":
                vrchat_process = process
                break

        self.logger.info("VRChat process detected: {}".format(vrchat_process))

        # TODO: This should be its own thread so the Observer can continue its work
        self.app.follow_log(event.src_path, vrchat_process)

def setup(icon):
    icon.visible = True

    app = VRCTrackerApp()
    app.run()

from PIL import Image, ImageDraw

def create_image(width, height, color1, color2):
    # Generate an image and draw a pattern
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 2, 0, width, height // 2),
        fill=color2)
    dc.rectangle(
        (0, height // 2, width // 2, height),
        fill=color2)

    return image

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    def on_clicked(icon, item):
        # nothing
        return

    # TODO: Load image from file, embed in built exe
    icon = pystray.Icon('VRCTracker',
                        icon=create_image(64, 64, 'black', 'white'),
                        title='VRCTracker',
                        menu=pystray.Menu(
                            pystray.MenuItem('Export Location History...',
                                             on_clicked),
                            pystray.Menu.SEPARATOR,
                            pystray.MenuItem('Exit',
                                             on_clicked)
                        ))

    icon.run(setup=setup)
