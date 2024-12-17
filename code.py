# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import json
import microcontroller
import os
import supervisor

SCRIPTS = "/apps"
SETTINGS = "/settings.json"

# Scan for scripts
scripts = tuple(filter(lambda filename: filename.endswith(".py"), os.listdir(SCRIPTS)))

# Reset the device in safe mode if no scripts are found
if not scripts:
    microcontroller.on_next_reset(microcontroller.RunMode.SAFE_MODE)
    microcontroller.reset()

# Attempt to use script from settings
script = ""
try:
    with open(SETTINGS) as file:
        settings = json.load(file)
        if "global" in settings and "script" in settings["global"]:
            script = settings["global"]["script"]
except (OSError, ValueError):
    settings = {}
if not script.endswith(".py"):
    script = script + ".py"

if not script in scripts:
    # Use first script and update settings
    script = scripts[0]
    if not "global" in settings:
        settings["global"] = {}
    settings["global"]["script"] = script
    try:
        with open(SETTINGS, "w") as file:
            json.dump(settings, file)
    except OSError:
        pass

# Load script
supervisor.set_next_code_file(
    filename=SCRIPTS + "/" + script,
    reload_on_success=True,
    reload_on_error=False,
    sticky_on_success=True,
    sticky_on_error=False,
    sticky_on_reload=False,
)
supervisor.reload()
