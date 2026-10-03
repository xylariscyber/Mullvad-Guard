# Mullvad Guard

Keeps your Mullvad account limited to a fixed number of devices.
If an extra device shows up on the account, the newest one is removed automatically.

---

## Files

| File | Purpose |
|---|---|
| `mullvad_guard.py` | The script. All the settings are at the top of this file |
| `requirements.txt` | The Python libraries the script needs (`requests`, `psutil`) |
| `mullvad_guard.log` | Created automatically next to the script |

There is no separate settings file: you edit the `SETTINGS` section at the top of
`mullvad_guard.py`.

---

## 1. Install

You need Python 3.9 or newer. Open a console in the script folder and install the
libraries listed in `requirements.txt`:

```
pip install -r requirements.txt
```

If `pip` is not recognized, use:

```
python -m pip install -r requirements.txt
```

---

## 2. Configure

Open `mullvad_guard.py` in any text editor. At the top you will find:

```python
ACCOUNT_NUMBER = "YOUR_MULLVAD_ACCOUNT_NUMBER"   # your Mullvad account number
MAX_DEVICES = 2                    # number of devices allowed on the account
CHECK_INTERVAL = 30                # seconds between two checks
PROTECTED_NAMES = []               # device names to NEVER kick, e.g. ["happy-fox", "calm-owl"]
DRY_RUN = False                    # True = only log what would be removed, nothing is deleted
ONLY_WHEN_MULLVAD_RUNNING = True   # False = also check when the Mullvad app is closed
MULLVAD_PROCESSES = [              # Mullvad process names (lowercase)
    "mullvad vpn.exe", "mullvad-daemon.exe", "mullvad-daemon",
    "mullvad vpn", "mullvad-gui",
]
```

| Setting | Description |
|---|---|
| `ACCOUNT_NUMBER` | Your Mullvad account number, between the quotes (spaces are ignored) |
| `MAX_DEVICES` | How many devices are allowed on the account |
| `CHECK_INTERVAL` | Seconds between two checks |
| `PROTECTED_NAMES` | Device names that must NEVER be removed. **Put your own PC here** (see below) |
| `DRY_RUN` | `True` = only logs what would be removed. `False` = devices are really kicked |
| `ONLY_WHEN_MULLVAD_RUNNING` | `True` = the script only acts while the Mullvad app is open |
| `MULLVAD_PROCESSES` | Process names used to detect that the Mullvad app is open |

Python syntax reminder: `True` and `False` start with a capital letter, text goes between
quotes, and the list of names looks like `["happy-fox", "calm-owl"]`.

Save the file after each change. If the script is already running, restart it so it
reads the new values.

---

## 3. Test it first

Open a console in the script folder and run one single check:

```
python mullvad_guard.py --once
```

You should see something like:

```
Check OK: 2/2 devices (happy-fox, calm-owl)
```

If you see your devices, the account number and the API work.
The names in the parentheses are the device names Mullvad gave to your devices.
Find the one that is your own PC and add it to `PROTECTED_NAMES`, for example:

```python
PROTECTED_NAMES = ["happy-fox"]
```

Then run the normal loop to watch it live (stop it with `Ctrl+C`):

```
python mullvad_guard.py
```

For your very first tests you can set `DRY_RUN = True`: the script then only logs what it
would remove. When everything looks right, set it back to `False`.

---

## 4. How it works

1. The script runs in an endless loop and wakes up every `CHECK_INTERVAL` seconds.
2. It looks for the Mullvad process (`Mullvad VPN.exe` / `mullvad-daemon.exe`).
   - Mullvad not running: the script does nothing and just waits (it does NOT exit).
   - Mullvad running: it continues to step 3.
3. It asks the Mullvad API for the list of devices on the account.
4. If the number of devices is higher than `MAX_DEVICES`:
   - devices are sorted by creation date,
   - protected devices are always kept,
   - the oldest devices fill the remaining slots,
   - all the others (the newest ones) are removed from the account.
5. A removed device loses its WireGuard key, so it can no longer connect.

The script stays alive in the background the whole time and uses almost no resources.

---

## 5. Running it in the background (Windows)

### 5.1 The idea

- `python.exe` opens a console window. If you close the window, the script stops.
- `pythonw.exe` runs the same script **without any window**. It is invisible and keeps
  running until you stop it, log off, or shut the PC down.

So running in the background means two things:
1. launching the script with `pythonw.exe`,
2. making Windows launch it automatically each time you log in.

First, find where `pythonw.exe` is. In a console:

```
where pythonw
```

Example result: `C:\Users\you\AppData\Local\Programs\Python\Python313\pythonw.exe`
(use your own path everywhere below).

### 5.2 Quick start (until next reboot)

In a console, in the script folder:

```
pythonw mullvad_guard.py
```

The console returns immediately and the script is now running hidden.
It will NOT come back after a reboot or log off, use 5.3 for that.

### 5.3 Start automatically at login

Choose ONE of the two options.

#### Option A - Startup folder (simplest)

1. Press `Win + R`, type `shell:startup`, press Enter. A folder opens.
2. Right-click in it > New > Shortcut.
3. In "location of the item", paste (with your own paths, keep the quotes):

   ```
   "C:\path\to\pythonw.exe" "C:\path\to\mullvad_guard.py"
   ```

4. Name it `MullvadGuard` and finish.
5. Optional: right-click the shortcut > Properties > set "Start in" to the script folder.

Next time you log in, the script starts by itself, hidden.

#### Option B - Task Scheduler (more robust, recommended)

This restarts the script if it crashes and never stops it after some days.
Open **PowerShell** and run (replace the two paths):

```powershell
$python = "C:\path\to\pythonw.exe"
$script = "C:\path\to\mullvad_guard.py"

$action   = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory (Split-Path $script)
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName "MullvadGuard" -Action $action -Trigger $trigger -Settings $settings
```

If you get "Access is denied", open PowerShell as administrator and run it again.

Important details:
- `-ExecutionTimeLimit ([TimeSpan]::Zero)` means "no time limit". Without it, Windows
  silently kills the task after 3 days. This is the most common mistake.
- `-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries` keeps it running on a laptop on battery.
- Do not move or rename the script after creating the task, or update the paths.

Start it right now without logging off:

```powershell
Start-ScheduledTask -TaskName "MullvadGuard"
```

### 5.4 Check that it is running

- Task Manager (`Ctrl + Shift + Esc`) > **Details** tab > look for `pythonw.exe`.
- Or in a console:

  ```
  tasklist | findstr pythonw
  ```

The log file only contains warnings (see section 6), so an empty log file is normal
when nothing happened. To verify that the API still answers, run
`python mullvad_guard.py --once` in a console.

### 5.5 Change a setting while it runs in the background

The script reads its settings only when it starts. After editing `mullvad_guard.py`:

1. Stop the running script (see 5.6).
2. Start it again (`pythonw mullvad_guard.py`, or `Start-ScheduledTask -TaskName "MullvadGuard"`
   if you used option B, or simply log off and on for option A).

### 5.6 Stop or remove it

- Stop now: Task Manager > Details > right-click `pythonw.exe` > End task.
  (`taskkill /IM pythonw.exe /F` also works but kills ALL pythonw programs.)
- Option A: delete the shortcut from the `shell:startup` folder.
- Option B, stop the running task:

  ```powershell
  Stop-ScheduledTask -TaskName "MullvadGuard"
  ```

- Option B, remove it completely:

  ```powershell
  Unregister-ScheduledTask -TaskName "MullvadGuard" -Confirm:$false
  ```

### 5.7 When does it NOT run?

The script runs on your computer, so it only works while the computer is on and your
session is open:

- PC off, log off or sleep: the script is not running and does not protect the account.
- It starts again at the next login (options A and B above).

To protect the account 24/7 even with your PC off, the script has to run on a machine that
is always on (a server, a Raspberry Pi...). In that case set
`ONLY_WHEN_MULLVAD_RUNNING = False`.

---

## 6. Logs

`mullvad_guard.log` only contains the important events:

```
2026-10-02 22:36:43,709 [WARNING] 3 devices detected (max 2) -> 1 to remove
2026-10-02 22:36:44,164 [WARNING] Device KICKED: awake pup
```

Normal checks (`Check OK: ...`) are only shown in the console, never written to the file.

With `DRY_RUN = True` the lines say `[DRY RUN] Device would be KICKED`, and since nothing is
removed, the same warning repeats at every check.

---

## 7. Troubleshooting

| Problem | Solution |
|---|---|
| `Set your Mullvad account number in ACCOUNT_NUMBER...` | `ACCOUNT_NUMBER` is still the placeholder |
| `API error (400)` or `API error (401)` | Wrong account number, or the account has expired |
| `API error (429)` | Too many requests. Increase `CHECK_INTERVAL`. The script already waits 2 minutes |
| `ModuleNotFoundError: No module named 'requests'` (or `'psutil'`) | Run `pip install -r requirements.txt` again, with the same Python you use to start the script |
| A syntax error when starting | Check the top of the script: quotes, commas, `True`/`False` with a capital letter |
| Nothing happens in the background | Run `python mullvad_guard.py` in a console to see the errors that `pythonw` hides |
| Script does nothing while Mullvad is open | Mullvad's process name may differ. Set `ONLY_WHEN_MULLVAD_RUNNING = False` |
| My new settings are ignored | Restart the script, it only reads them at startup |
| Task stopped after a few days | The task was created without `-ExecutionTimeLimit ([TimeSpan]::Zero)`, see option B |

---

## 8. Security

- Set your account number locally in `mullvad_guard.py`; keep the placeholder in the
  public repository and never commit your real account number.
- The account number is sensitive. If it is exposed, create a new Mullvad account.
- Removing a device does not stop someone who knows your account number from adding
  another one. If your number leaked, the real fix is a new account.
