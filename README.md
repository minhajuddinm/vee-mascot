# Vee desktop mascot

Pixel Vidhi that floats over your windows and reacts to Claude.

## Setup (Windows)

Installed at `D:\vee-mascot`. Double-click `start_vee.bat`: it finds a working Python, installs `uiautomation`, and starts Vee. Right-click Vee, then Test state, to check all four states.

## Code tab (Claude Code hooks)

1. Open `%USERPROFILE%\.claude\settings.json`
2. Merge the `hooks` block from `claude_hooks_snippet.json` into it
3. Paths already point to `D:/vee-mascot` and `D:/Software/Pycharm/python.exe`
4. Restart the Code session

| Hook | Vee |
|---|---|
| UserPromptSubmit, PreToolUse | Working |
| Notification (permission_prompt) | Needs you |
| Stop | Done |

## Chat tab (UI watcher)

- Polls the Claude window once a second for a Stop button (Working) or Allow buttons (Needs you)
- Stop button disappears: Done
- Done clears after Claude has been focused for 3 seconds

If Chat replies never trigger Working:

1. Run `python vee_mascot.py --debug`
2. Send a chat message and watch the console for `buttons: [...]`
3. Check `vee_buttons.log`, copy the label of the stop button into `STOP_LABELS` at the top of `vee_mascot.py`
4. Same for the approve buttons and `NEED_LABELS`

If the console shows no buttons at all, Electron has not exposed its accessibility tree. Start Claude once with `--force-renderer-accessibility` added to its shortcut target.

## Controls

- Hover over Vee: toolbar appears
  - Pencil: bring the Claude app to the front
  - Bubble: progress updates on or off (Done and permission alerts still show)
  - Arrow: menu
- Click Vee: she says something; drag her to move (position is saved)
- Right-click or arrow menu:
  - Choose outfit, Size
  - Show progress updates, Show prompt text, Walk around
  - Notify when Claude is done (Windows toast), Sound when Claude is done
  - Open in browser, Open activity log (`vee_activity.log`), Test the Done message, Test state
  - Copy diagnostics, Bring pet back, Quit

Progress text ("Editing sprites.py", "Running npm test") and prompt text come from Claude Code hooks. In the Chat tab she shows "Thinking… m:ss".
Done toasts and sounds only fire when Claude is not the window in front.

## Start with Windows

1. Press Win+R, type `shell:startup`, Enter
2. Create a shortcut there with target:
   `D:\vee-mascot\start_vee.bat`

## Files

- `vee_mascot.py`: window, state logic, hook server (port 7777), Chat watcher
- `sprites.py`: face, 7 outfits, state animations
- `vee_hook.py`: helper the hooks call; always exits 0 so it never blocks Claude Code
- `vee_config.json`: created on first drag or menu change
