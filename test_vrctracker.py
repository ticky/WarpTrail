import unittest

from vrctracker import VRCTrackerApp

import io
import os
import sqlite3
import sys
from tempfile import TemporaryDirectory

DB_CHECKIN_FIXTURES = """
INSERT INTO "worlds" VALUES ('wrld_4432ea9b-729c-46e3-8eaf-846aa0a37fdd', 'VRChat Home');
INSERT INTO "worlds" VALUES ('wrld_47c2a8bd-1f76-4e2c-94bb-5ae3b43e762e', NULL);
INSERT INTO "worlds" VALUES ('wrld_56b348fc-b1cb-4242-8587-9eb8e01ef399', 'Just Rain');
INSERT INTO "worlds" VALUES ('wrld_26120cd6-6097-406e-8a48-a3657cb60511', 'Reflections 2');
INSERT INTO "checkins" VALUES ('wrld_47c2a8bd-1f76-4e2c-94bb-5ae3b43e762e', '2022-04-05T21:44:16-07:00', NULL);
INSERT INTO "checkins" VALUES ('wrld_4432ea9b-729c-46e3-8eaf-846aa0a37fdd', '2022-04-05T23:02:13-07:00', '2022-04-05T23:02:28-07:00');
INSERT INTO "checkins" VALUES ('wrld_26120cd6-6097-406e-8a48-a3657cb60511', '2022-04-10T18:08:22-07:00', '2022-04-10T18:38:56-07:00');
INSERT INTO "checkins" VALUES ('wrld_56b348fc-b1cb-4242-8587-9eb8e01ef399', '2022-04-15T16:09:26-07:00', '2022-04-15T16:10:35-07:00');
INSERT INTO "checkins" VALUES ('wrld_56b348fc-b1cb-4242-8587-9eb8e01ef399', '2022-04-15T18:13:51-07:00', '2022-04-15T18:14:25-07:00');
INSERT INTO "checkins" VALUES ('wrld_26120cd6-6097-406e-8a48-a3657cb60511', '2022-04-15T16:10:35-07:00', '2022-04-15T16:39:21-07:00');
"""


class VRCTrackerTests(unittest.TestCase):
    def test_get_user_data_dir(self):
        self.assertTrue(os.path.isdir(VRCTrackerApp.get_user_data_dir()))

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_get_vrchat_data_dir_windows(self):
        self.assertEqual(
            VRCTrackerApp.get_vrchat_data_dir(),
            os.path.abspath(
                os.path.expandvars("%LOCALAPPDATA%\\..\\LocalLow\\VRChat\\VRChat")
            ),
        )

    def test_format_as_markdown(self):
        with TemporaryDirectory(ignore_cleanup_errors=True) as vrchat_data_dir:
            with TemporaryDirectory(ignore_cleanup_errors=True) as user_data_dir:
                app = VRCTrackerApp(
                    user_data_dir=user_data_dir, vrchat_data_dir=vrchat_data_dir
                )
                db_conn = sqlite3.connect(app.database_path)
                db = db_conn.cursor()
                db.executescript(DB_CHECKIN_FIXTURES)
                db_conn.commit()

                file = io.StringIO("")

                app.format_as(".md", file)

                file.seek(0)
                result = file.read()

                self.assertEqual(
                    result,
                    """# VRCTracker Location History

- [wrld_47c2a8bd-1f76-4e2c-94bb-5ae3b43e762e](https://vrch.at/wrld_47c2a8bd-1f76-4e2c-94bb-5ae3b43e762e)  
  from 05/04/2022, 21:44 until (unknown)
- [VRChat Home](https://vrch.at/wrld_4432ea9b-729c-46e3-8eaf-846aa0a37fdd)  
  from 05/04/2022, 23:02 until 05/04/2022, 23:02
- [Reflections 2](https://vrch.at/wrld_26120cd6-6097-406e-8a48-a3657cb60511)  
  from 10/04/2022, 18:08 until 10/04/2022, 18:38
- [Just Rain](https://vrch.at/wrld_56b348fc-b1cb-4242-8587-9eb8e01ef399)  
  from 15/04/2022, 16:09 until 15/04/2022, 16:10
- [Just Rain](https://vrch.at/wrld_56b348fc-b1cb-4242-8587-9eb8e01ef399)  
  from 15/04/2022, 18:13 until 15/04/2022, 18:14
- [Reflections 2](https://vrch.at/wrld_26120cd6-6097-406e-8a48-a3657cb60511)  
  from 15/04/2022, 16:10 until 15/04/2022, 16:39
""",
                )

    def test_format_as_text(self):
        with TemporaryDirectory() as vrchat_data_dir:
            with TemporaryDirectory() as user_data_dir:
                app = VRCTrackerApp(
                    user_data_dir=user_data_dir, vrchat_data_dir=vrchat_data_dir
                )
                db_conn = sqlite3.connect(app.database_path)
                db = db_conn.cursor()
                db.executescript(DB_CHECKIN_FIXTURES)
                db_conn.commit()

                file = io.StringIO("")

                app.format_as(".txt", file)

                file.seek(0)
                result = file.read()

                self.assertEqual(
                    result,
                    """wrld_47c2a8bd-1f76-4e2c-94bb-5ae3b43e762e (https://vrch.at/wrld_47c2a8bd-1f76-4e2c-94bb-5ae3b43e762e), from 05/04/2022, 21:44 until (unknown)
VRChat Home (https://vrch.at/wrld_4432ea9b-729c-46e3-8eaf-846aa0a37fdd), from 05/04/2022, 23:02 until 05/04/2022, 23:02
Reflections 2 (https://vrch.at/wrld_26120cd6-6097-406e-8a48-a3657cb60511), from 10/04/2022, 18:08 until 10/04/2022, 18:38
Just Rain (https://vrch.at/wrld_56b348fc-b1cb-4242-8587-9eb8e01ef399), from 15/04/2022, 16:09 until 15/04/2022, 16:10
Just Rain (https://vrch.at/wrld_56b348fc-b1cb-4242-8587-9eb8e01ef399), from 15/04/2022, 18:13 until 15/04/2022, 18:14
Reflections 2 (https://vrch.at/wrld_26120cd6-6097-406e-8a48-a3657cb60511), from 15/04/2022, 16:10 until 15/04/2022, 16:39
""",
                )

    def test_format_as_json(self):
        with TemporaryDirectory() as vrchat_data_dir:
            with TemporaryDirectory() as user_data_dir:
                app = VRCTrackerApp(
                    user_data_dir=user_data_dir, vrchat_data_dir=vrchat_data_dir
                )
                db_conn = sqlite3.connect(app.database_path)
                db = db_conn.cursor()
                db.executescript(DB_CHECKIN_FIXTURES)
                db_conn.commit()

                file = io.StringIO("")

                app.format_as(".json", file)

                file.seek(0)
                result = file.read()

                self.assertEqual(
                    result,
                    '[{"world_name":null,"world_url":"https://vrch.at/wrld_47c2a8bd-1f76-4e2c-94bb-5ae3b43e762e","start_datetime":"2022-04-05T21:44:16-07:00","end_datetime":null},{"world_name":"VRChat Home","world_url":"https://vrch.at/wrld_4432ea9b-729c-46e3-8eaf-846aa0a37fdd","start_datetime":"2022-04-05T23:02:13-07:00","end_datetime":"2022-04-05T23:02:28-07:00"},{"world_name":"Reflections 2","world_url":"https://vrch.at/wrld_26120cd6-6097-406e-8a48-a3657cb60511","start_datetime":"2022-04-10T18:08:22-07:00","end_datetime":"2022-04-10T18:38:56-07:00"},{"world_name":"Just Rain","world_url":"https://vrch.at/wrld_56b348fc-b1cb-4242-8587-9eb8e01ef399","start_datetime":"2022-04-15T16:09:26-07:00","end_datetime":"2022-04-15T16:10:35-07:00"},{"world_name":"Just Rain","world_url":"https://vrch.at/wrld_56b348fc-b1cb-4242-8587-9eb8e01ef399","start_datetime":"2022-04-15T18:13:51-07:00","end_datetime":"2022-04-15T18:14:25-07:00"},{"world_name":"Reflections 2","world_url":"https://vrch.at/wrld_26120cd6-6097-406e-8a48-a3657cb60511","start_datetime":"2022-04-15T16:10:35-07:00","end_datetime":"2022-04-15T16:39:21-07:00"}]',
                )


if __name__ == "__main__":
    unittest.main()
