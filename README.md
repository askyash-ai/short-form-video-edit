# short-form-video-edit

Setup guide (one page).

A Claude Code skill that turns raw phone takes into a finished vertical video (Reels, TikTok, Shorts): it picks the
best take per line, cuts the dead air, cleans the voice, adds captions and motion graphics, renders, and checks every
frame. You film and approve; Claude does the edit. **Set-up time: about 30-45 minutes, once.**

## Be honest with yourself first: what it needs

| You need | Why | Cost |
|---|---|---|
| **Claude Code** with a paid Claude plan | it runs the whole edit | a 4K edit is long: Pro works, heavy use needs Max |
| A computer with **8 GB RAM** or more (16 GB is smoother), ~10 GB free disk | 4K renders are heavy | - |
| **Node.js 22+**, **Python 3.10+**, **FFmpeg** (full build), **Google Chrome**, **Git** | the tools it runs | free |
| The **HyperFrames student kit** (Nate Herk, open source) | the renderer it uses | free |
| A transcriber: an **ElevenLabs API key**, *or* whisper.cpp offline | word-level timings for cuts and captions | ElevenLabs is paid per minute (check their pricing); whisper is free |
| Footage from an **iPhone** (4K 60 fps or 1080p 30 fps), one take per script line | that's what it's tuned for | - |

Tested on Windows 11. macOS should work (the commands are below), but it hasn't been tested there yet. Footage from
other phones may need tweaking.

## Install

**1. Claude Code.** Install it from claude.com/claude-code and sign in.

**2. The tools.** Open a terminal and run:

```bash
winget install OpenJS.NodeJS.LTS
winget install Python.Python.3.12
winget install Gyan.FFmpeg
winget install Google.Chrome
winget install Git.Git
```
On a Mac: `brew install node python ffmpeg git` and install Chrome from google.com/chrome. Then, on both:
```bash
python -m pip install numpy pillow auto-editor
```
Close and reopen the terminal so the new tools are found.

**3. The HyperFrames kit.** Pick a folder **without** spaces in the path, then:

```bash
git clone https://github.com/nateherkai/hyperframes-student-kit
cd hyperframes-student-kit
npm ci
```

**4. Tell the skill where the kit is.** On Windows (use your real path): `setx HF_KIT "C:\code\hyperframes-student-kit"`. On a Mac, add
`export HF_KIT="$HOME/code/hyperframes-student-kit"` to `~/.zshrc`. Then reopen the terminal.

**5. Your transcription key.** In the kit folder, copy `.env.example` to `.env`, open it in a text editor and paste
your key after `ELEVENLABS_API_KEY=`. **Type keys into `.env` yourself. Never paste a key into the Claude chat, and never
share your `.env`.** No key? Skip this, and in step 7 ask Claude to "set up the offline whisper transcriber" (a 1.5 GB download).

**6. Install the skill.** The easy way: start Claude Code and type
> Install the skill from https://github.com/askyash-ai/short-form-video-edit into my ~/.claude/skills folder.

Or by hand: on this page click **Code → Download ZIP**, unzip it, rename the folder from
`short-form-video-edit-main` to `short-form-video-edit`, and move it to:
- Windows: `C:\Users\<you>\.claude\skills\short-form-video-edit`
- Mac: `~/.claude/skills/short-form-video-edit`

**7. Check it.** Start Claude Code in the kit folder and type:
> Run the setup check from the short-form-video-edit skill, install anything missing, run its tests, and fix
> anything that fails on my computer until every check and test passes.

Claude works through it until every row is OK and the tests end `OK`; you approve the installs it asks about.

## Make it yours (10 minutes, before your first video)

- **`CHANNEL.md`**: your niche, audience, tone and series. Or just say "set up my channel" and Claude asks you.
- **`private/denylist.txt`**: one term per line that must never be on screen (your employer, clients, real product
  codes). The privacy check blocks the render if any appear. It starts empty, so fill it in.
- **`STYLE-GUIDE.md`**: the colours, captions and motion. It's the author's look; change it, then tell Claude
  "update the short-form-video-edit skill to match".
- **Logos:** no brand logos ship with the skill. To show a tool (e.g. Claude) on screen, download its logo from the
  maker's official brand page and save it as a transparent PNG in `assets/` (e.g. `assets/claude-logo.png`).

## Your first edit

Put your takes in `hyperframes-student-kit/video-projects/<name>/raw/`, start Claude Code in the kit folder and say:
> Edit this reel with the short-form-video-edit skill: video-projects/<name>/raw. Here's my script: ...

Before you film, it can also check your script and a 5-second test clip ("check my script", "check this test shot").
It stops twice to ask you: once to pick the takes, once to approve the plan. A 30-second 4K reel takes about an hour
of machine time; 1080p is much faster.

## If something goes wrong

| You see | Fix |
|---|---|
| `No HyperFrames kit at ...` | step 4: `HF_KIT` isn't set, or the terminal wasn't reopened |
| `zscale` not found / colour errors | your FFmpeg is the slim build: install the full build (step 2) |
| Claude app freezes during a 4K render | close other apps; the skill runs heavy jobs in the background, one at a time |
| Transcription fails with 401 | the ElevenLabs key in `.env` is wrong or out of credits |

Licences and credits: `LICENSE` and `NOTICE.md`. Provided as is, with no warranty. Always watch the finished video
before you post it: Claude can't hear the audio.
