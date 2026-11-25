<!-- Wording approved by the owner 2026-11-25; the WS50 slice B additions approved by the owner 2026-11-25 (after review). -->
# Install SceneVoice on a Mac

This page is for people who do not write code. You will paste a few lines into Terminal. You do this once.

## Before you start

- You need a Mac and an internet connection.
- Terminal is the app in Applications, in the Utilities folder.
- You do not need to install Python, Node or ffmpeg yourself.

## Step 1: Install uv (once)

uv is a small helper program that installs SceneVoice and the right version of Python for it. Open Terminal, paste this line and press Return:

<!-- Owner approved this exact uv installer line on 2026-11-25. Agents never run it. -->
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

When it finishes, close Terminal and open it again.

## Step 2: Install SceneVoice (once)

<!-- UNVERIFIED: this release file does not exist until WS50 publishes version 0.2.0. The WS49 proof installs the local 0.1.0 wheel instead. -->
Paste this line and press Return:

```
uv tool install --python 3.12 https://github.com/dtbndr/open-scene-voice/releases/download/v0.2.0/scenevoice-0.2.0-py3-none-any.whl
```

The line says `--python 3.12` because SceneVoice has only been tested with Python 3.12, and without it uv would pick the newest Python it finds.

## Step 3: Let Terminal find SceneVoice (once)

Paste this line and press Return:

```
uv tool update-shell
```

This adds one line to a settings file in your home folder (`~/.zshenv`) so that Terminal knows where SceneVoice lives. If the installer in Step 1 already set this up, the line only says that the folder is already on your path, and nothing changes. Either way, close Terminal and open a new Terminal window. The new window is needed: the old one does not see the change.

## Step 4: Start SceneVoice

In Terminal, type this and press Return:

```
scenevoice web
```

Terminal prints "SceneVoice is running." and then a line starting "Open it here:" followed by a link. Your browser opens on SceneVoice. If it does not, click or copy that link into your browser. The link is private to this run: a new run prints a new link.

**Keep the Terminal window open while you work.** Closing it stops SceneVoice.

The first time you run SceneVoice, macOS may ask whether Terminal can access your Documents folder. Choose Allow, or SceneVoice cannot save your work.

## If SceneVoice stops

If you closed the Terminal window, the SceneVoice page in your browser says:

> SceneVoice has stopped.
> The Terminal window was probably closed. Your work is saved in the SceneVoice folder in your Documents folder.
> To carry on: open Terminal, type scenevoice web and press Return.

The page has a "Copy the command" button that copies `scenevoice web` so you can paste it into Terminal.

Your scripts are not lost. Start SceneVoice again with `scenevoice web` and open the new link it prints.

## Next

Add your voice-provider keys inside SceneVoice, then follow the screens. The script rules are in the [script guide](script-format.md). What changed in each release is in the [release notes](release-notes.md).
