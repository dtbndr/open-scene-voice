# Writing a script for SceneVoice

A script is a plain text file that is read aloud, scene by scene. Each scene becomes its own audio clip.

## What makes a scene

A scene starts with a line that begins with `## ` (two hashes and a space) at the very start of the line, followed by a title. Everything under that line, up to the next `## ` line or the end of the file, is the scene's text.

```script-valid scenes=2
## Opening
Welcome back to the channel.

## The reveal
Today we open the box.
```

The title is a label for you and the timeline. It is not spoken, and SceneVoice does not read meaning into it, so `## Scene 2 Dance` is as good a title as `## Dance`.

## Everything else is spoken exactly as written

Whatever sits under a scene line is read aloud, character for character. That includes square brackets, stage directions and notes to yourself. There is no comment syntax and no way to hide a line from the voice. If you do not want it said, take it out of the file.

The only text that is not spoken is anything before the first `## ` line. Use that space for a working title or notes to yourself. SceneVoice ignores it completely. If you write a pronunciation list there, it does not change how any word is said.

```script-valid scenes=1
My video: unboxing the new camera
Note to self: check the logo shot before recording.

## Intro
Hello there. [pause] This bracket is read out loud, so it says "pause".
```

## What gets rejected

SceneVoice stops and tells you rather than guessing:

- No `## ` line at all, so there are no scenes.

```script-invalid rule=no-marker
Welcome back to the channel.
Today we open the box.
```

- A scene line with nothing after `## ` (the space is easy to miss), so the scene has no title.

```script-invalid rule=blank-title line=4
## Opening
Welcome back to the channel.

## 
Today we open the box.
```

In that example the heading line is `## ` followed only by spaces, so the title is empty. A bare `##` with nothing after it is not a scene line at all and is read aloud as ordinary text.

- A scene with no text under its heading, or only blank lines.

```script-invalid rule=blank-body line=4
## Opening
Welcome back to the channel.

## The reveal
```

- A tab character (U+0009) anywhere in the file. Tabs are disallowed control characters, even inside a scene's text. In this example the second line starts with a tab:

```script-invalid rule=control line=2
## Opening
	Hello.
```

A line that starts with a space, or with `#` and no space, is just spoken text, not a scene line.

## Saving the file

Save as plain UTF-8 text with LF (Unix) line endings. Files with Windows line endings (CRLF) or old Mac-style bare carriage returns are rejected, so switch your editor to LF before saving. Do not add a byte order mark, and avoid hidden control characters, which sometimes arrive when pasting from a web page or word processor. Files with these problems are rejected.

## Starting from an idea

If you have an idea but no script yet, paste this whole guide into any chat assistant along with your idea, and ask it to write a script that follows the guide. Read through what it gives you and edit it, then save it as described above. SceneVoice will point out anything that doesn't fit the format.
