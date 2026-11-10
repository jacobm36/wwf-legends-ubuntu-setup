# WWF Legends - Challenge 64: Ubuntu Setup Guide

This guide covers a fresh Ubuntu desktop setup from the extracted game folder
through the first launch. It uses Wine, a dedicated Wine prefix, Project64, and
the included Linux launcher for music and GPU selection.

The setup helper copies and configures files you already have; it does not
download the game, ROM, texture pack, or music. Obtain the game/mod files and
media only from sources authorized to distribute them. The music pack is a
required part of this mod, not an optional extra.

## What this setup does

- Keeps this game in its own Wine prefix, separate from other Windows games.
- Launches the included Project64 build and the `WWF Legends - Challenge 64`
  ROM from the correct Windows-style path.
- Uses the supplied Rice graphics plugin and native `msvcr71.dll` and
  `msvcp71.dll` libraries.
- Uses Winebundle's GPU selection helper.
- Uses the Linux launcher to play supplied MP3s without the Windows
  PowerShell music tool.
- Enters borderless fullscreen after the game RAM is ready, without changing
  the desktop resolution. Rice renders at the primary display's resolution.
- Adds a WWF Legends application-menu entry and writes launch logs.

This is not installed through Winebundle's **Add a game** wizard. That wizard
creates a different prefix and does not run the Linux music helper. Winebundle
is still required for its installed GPU helper.

## 1. Check the computer

Use a 64-bit Ubuntu or Ubuntu-based desktop with access to Ubuntu packages.
Other Debian-based distributions may work, but package names and Wine
configuration can differ. This guide assumes a normal graphical desktop
session.

Install Wine and the audio/error-dialog dependencies:

```sh
sudo apt update
sudo apt install wine python3-gi gir1.2-gstreamer-1.0 \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-ugly zenity
```

`gstreamer1.0-plugins-ugly` supplies MP3 decoding on the tested Ubuntu setup.
If APT reports that Wine's 32-bit packages are unavailable, enable i386
support, refresh package metadata, and retry:

```sh
sudo dpkg --add-architecture i386
sudo apt update
```

Then install Wine again. Winebundle's **System check** can also identify
missing Wine or graphics support.

## 2. Install Winebundle

Download the latest Ubuntu `.deb` from the
[Winebundle releases page](https://github.com/jacobm36/winebundle-orchestrator/releases?q=ubuntu&expanded=true)
and install it. For example, if it is in `~/Downloads`:

```sh
sudo apt install ~/Downloads/winebundle_*_all.deb
```

Open Winebundle once and use **System check** to resolve any missing graphics
or Wine requirements. Keep Winebundle installed: the game launcher imports
its GPU-selection helper from `/usr/share/winebundle/lib`.

## 3. Prepare the extracted game folder

Obtain and extract the authorized game/mod package. The extracted folder
should be named `Ch64 - Public` and contain at least:

```text
Ch64 - Public/
  Project64/
    Project64.exe
    Config/Project64.cfg
    Plugin/RiceVideo.dll
    Roms/WWF Legends - Challenge 64.z64
    msvcr71.dll
    msvcp71.dll
```

The full Project64 folder also needs its supplied plugins, cheat database,
textures, and save/config files. Keep the folder structure intact; do not
move the ROM out of `Project64/Roms`.

Place these setup files directly inside `Ch64 - Public`, alongside the
`Project64` folder:

- `setup-ubuntu.py`
- `launch-ubuntu.py`
- `legends_runtime.py`
- `enable-fullscreen.py`
- `borderless.py`
- `borderless.exe` (build from this repository's `borderless.c`)

Build the borderless helper from the cloned repository before copying the
files or running setup:

```sh
sudo apt install gcc-mingw-w64-i686
sh build-borderless.sh
```

The compiler is only needed to build the helper, not to play. The generated
executable contains only our window-management code; it is not a game asset.

The setup script checks for the expected files and stops before installing if
they are missing. It will not obtain or recreate any game assets.

For project information, see the
[WWF Legends 64 project website](https://wwflegends64.wixsite.com/wwflegends).
Its Downloads page lists a full base-game package as well as a separate music
pack. This guide does not link to or redistribute the full-game package,
because it appears to include the original game's copyrighted files. Use a
lawfully obtained copy of the original game, and only obtain mod and music
files from sources authorized to distribute them.

### Required music files

The music is an essential part of the mod and is distributed separately from
the base game package. Obtain the soundtrack pack for the same mod version,
then extract its MP3 files into:

```text
Project64/Music Tool/Music/
```

Keep the filenames from the soundtrack pack; they correspond to the game's
music commands (for example `0x1.mp3` or `0x1A.mp3`). The Linux helper matches
filenames without regard to letter case. Extract the complete pack so all
music commands have their tracks. The setup script checks that the folder
contains MP3 files and stops before creating a Wine prefix if none are found;
it cannot determine whether a partial pack is missing individual tracks.

## 4. Run the setup helper

Open a terminal in the extracted `Ch64 - Public` folder. For example:

```sh
cd "$HOME/Downloads/Ch64 - Public"
python3 setup-ubuntu.py
```

The helper will:

1. Check Wine, Winebundle, GStreamer bindings, required game files, and MP3
   music files.
2. Create a fresh 64-bit Wine prefix at
   `~/.local/share/wineprefixes/wwf-legends`.
3. Copy the extracted folder into the prefix at
   `drive_c/Ch64 - Public`.
4. Update the Project64 ROM/save/plugin paths for that location, keeping a
   timestamped config backup.
5. Disable the conflicting native automatic-fullscreen preference, with a
   config backup. The Ubuntu launcher handles fullscreen after texture loading.
6. Create `~/.local/bin/wwf-legends` and
   `~/.local/share/applications/wwf-legends.desktop`.

It does not run with `sudo`. The Wine prefix and application-menu entry belong
to your user account.

The helper refuses to overwrite an existing prefix or menu launcher. If the
default prefix already exists, do not delete it to make setup continue: it may
contain save data. Back it up first, or choose another empty prefix:

```sh
python3 setup-ubuntu.py --prefix "$HOME/.local/share/wineprefixes/wwf-legends-test"
```

## 5. Verify Project64 settings

The supplied config already includes the mod settings. The helper fixes the
Linux-specific file paths and enables the final supplied cheat flag to match
this setup. Before playing:

1. Launch **WWF Legends - Challenge 64** from the application menu.
2. Wait for Project64 and the texture scan to finish. The first scan can take
   1-2 minutes. Do not open the cheats menu during this initial load; Project64
   may pause.
3. Open the cheats menu after startup and ensure the main **WWF Legends**
   cheat is enabled (green tick). The setup package's **Cheat Code Settings**
   image shows the expected state. F2 toggles pause.
4. Confirm the game memory setting is at least 8 MB under
   **Options > Settings > Config: WWF No Mercy**.
5. After texture loading, the Ubuntu launcher removes the emulator's title,
   menu, and status bars and enters borderless fullscreen. The original
   automatic-fullscreen preference is disabled to avoid conflicting with this
   Wine/Rice workaround. Exit with **Alt+F4**. To use the emulator's menus, launch with
   `WWF_LEGENDS_WINDOWED=1 ~/.local/bin/wwf-legends` instead.

## 6. Configure a controller

Open **Options > Configure Controller Plugin** in Project64. Configure a
gamepad there if you use one. The working keyboard mapping for this setup is:

| N64 control | Keyboard |
|---|---|
| Start | Numpad Enter |
| A | A |
| B | Z |
| Z trigger | Right Shift |
| D-pad | Arrow keys |
| Analog stick | Numpad 8 / 2 / 4 / 6 (Num Lock off) |
| L / R | 1 / 2 |
| C-up / C-down / C-left / C-right | 3 / E / W / R |

If you change controller settings, use **Options > Configure Controller
Plugin** and verify them in a match.

## 7. Launch, exit, and find logs

Start the game from the application menu, or run:

```sh
~/.local/bin/wwf-legends
```

Exit with **File > Exit** or close Project64. The Linux music player stops
when the emulator exits.

Logs are written to:

```text
~/.local/state/wwf-legends/launch.log
~/.local/state/wwf-legends/launch.previous.log
```

Save data and the installed game live in the dedicated prefix:

```text
~/.local/share/wineprefixes/wwf-legends/drive_c/Ch64 - Public/
```

Back up this folder (especially `Project64/Save`) before moving the game,
changing prefixes, or troubleshooting. The script's config backups are kept
beside `Project64/Config/Project64.cfg`.

## Export to Batocera (experimental)

This export targets **Batocera 43 or newer on an x86-64 PC**. It does not
support ARM boards. No Winebundle installation is needed on the target.
The export has automated local tests, but an actual Batocera game/music/
controller test is still required before treating it as supported.

### Create the export on Ubuntu

Complete the Ubuntu setup first, then **close Project64** so its config and
saves are not changing while they are copied. From this repository, run:

```sh
python3 export-batocera.py --output "$HOME/wwf-legends-batocera-export"
```

For a nondefault installed prefix, add:

```sh
python3 export-batocera.py \
  --prefix "$HOME/.local/share/wineprefixes/wwf-legends-test" \
  --output "$HOME/wwf-legends-batocera-export"
```

The helper copies only your installed `Project64` folder and the current
Batocera launch scripts. It preserves configuration, plugins, textures,
cheats, saves, and soundtrack. It does **not** copy Ubuntu's Wine registry,
Wine DLLs, drive links, or application-menu launcher. All game files stay at
`C:\Ch64 - Public\Project64`, so the Ubuntu-configured paths remain valid.
Game-folder symlinks are rejected; supply regular files instead.

Use a new output folder outside this repository and the source prefix.
Existing Batocera game data or Ports entries are never overwritten. A
failed copy can leave a partial export; the error identifies the paths to
inspect. Do not delete or overwrite existing saves just to retry.

The default Batocera runner is `wine-proton`. To create a separate export
using `wine-tkg`, add `--runner wine-tkg`. Once a target prefix has been
initialized, changing runners requires a separate export to avoid silently
converting the existing prefix.

### Transfer and check on Batocera

The output is an overlay with these locations:

```text
roms/ports/WWF Legends - Challenge 64.sh
roms/ports/WWF Legends - Challenge 64.sh.keys
system/wwf-legends/prefix/drive_c/Ch64 - Public/
  launch-batocera.py
  legends_runtime.py
  Project64/
```

Copy the **contents** of the export into `/userdata` on Batocera. Through
the network share `\\BATOCERA\share`, merge its `roms/` and `system/`
folders into the matching shared folders; do not replace whole folders.
Stop if `system/wwf-legends` or the matching Ports entry already exists:
back up that installation and its saves first. Never publish the export;
it contains your privately supplied game and media files.

In Batocera's **F1 > Applications > xterm**, run:

```sh
python3 "/userdata/system/wwf-legends/prefix/drive_c/Ch64 - Public/launch-batocera.py" --check
```

If exported with `--runner wine-tkg`, add that same argument to the check.
Over SSH, use `DISPLAY=:0` before `python3` for the target graphical/audio
session. The check verifies architecture/version, executable Wine and
wineserver, required game files, and muted decoding/playback of a supplied
MP3 through GStreamer. It does not create a prefix or start Project64.
Python PyGObject, the Gst 1.0 typelib, `playbin`, an MP3 decoder, and a working
audio sink must be present. If these are missing, the launcher reports an
error rather than running the game without its required music. Ubuntu APT
commands do not apply to Batocera's read-only system.

### Play and verify

Refresh **Game Settings > Update Games Lists**, then launch the game from
**Ports**. If a USB/network transfer removed the executable bit, run:

```sh
chmod +x "/userdata/roms/ports/WWF Legends - Challenge 64.sh"
```

The first launch initializes a fresh 64-bit Wine prefix in
`/userdata/system/wwf-legends/prefix`; allow several minutes, then the
usual Project64 texture scan. The Ubuntu installation is unchanged.

Configure your gamepad inside **Project64 > Options > Configure Controller
Plugin**. Batocera's N64 controller mappings are not automatically imported.
The supplied `.sh.keys` maps **Hotkey + Start** to **Alt+F4** to close the
focused Project64 window. Closing the emulator also stops the soundtrack;
**Alt+Enter** still toggles fullscreen.

Verify a match has the expected graphics, cheats, music transitions and
looping, controller input, clean exit, and working saves after relaunch.
Reading/writing `/proc/<Project64 PID>/mem` must work with the selected
Wine build. The launcher starts Wine directly to retain its child PID, but
the memory signatures and addresses depend on the supplied Project64/mod
build. The dependency check alone cannot validate those in-game behaviors.

Ports launches use Batocera's current display/GPU environment rather than
Ubuntu's Winebundle GPU helper. They do not inherit the Windows system's
per-game Wine, display, or controller settings. This is not a Windows
`autorun.cmd` entry, and Winebundle's `.wsquashfs` compression is not part of
this export: a Windows-only launcher would bypass the Linux music helper.

Launch errors and music warnings appear in
`/userdata/system/logs/wwf-legends.log`, with the previous launch in
`wwf-legends.previous.log`. Manual `--check` output appears in the terminal.
Save data remains under
`/userdata/system/wwf-legends/prefix/drive_c/Ch64 - Public/Project64/Save`;
back up the entire `system/wwf-legends` folder before changing anything.

## Troubleshooting

- **The setup script reports missing requirements:** Install the listed
  Ubuntu packages and Winebundle, then rerun the script from the extracted
  folder.
- **The script says game files are missing:** Check that the setup scripts are
  beside `Project64/` and that the required Project64, ROM, plugin, and DLL
  paths above exist.
- **The script says the music files are missing:** Extract the required
  soundtrack pack's MP3 files into `Project64/Music Tool/Music` in the
  extracted folder, then rerun setup.
- **The script says the prefix or launcher already exists:** It did not
  overwrite it. Check the existing prefix and save data; use `--prefix` to
  select a different empty location.
- **The application menu does not show the game:** Run
  `~/.local/bin/wwf-legends` from a terminal. Check the launcher log and
  confirm the desktop file is under `~/.local/share/applications`.
- **Music does not play:** Confirm the MP3 files are in
  `Project64/Music Tool/Music` inside the installed prefix and filenames
  match the game's hexadecimal music commands. Look for `No custom track`
  warnings in `launch.log`.
- **The picture is incorrect or the game fails when switching modes:** Close
  the game, launch with `WWF_LEGENDS_WINDOWED=1 ~/.local/bin/wwf-legends`,
  and review the supplied graphics settings.
  The included build uses RiceVideo; other graphics-plugin changes may affect
  the configured high-resolution textures.
- **The launcher expects a windowed status bar:** Use the windowed command
  above and enable Project64's status bar before retrying normally. The helper
  uses its native hide event to wait for the Rice fullscreen transition.
- **The game appears frozen at startup:** Allow 1-2 minutes for texture
  scanning. Avoid opening the cheats menu during this period.
