# Handoff: walk in wake + Claude control

For the Claude Code session running on Yash's PC in C:\jarvis. The cloud session built these pieces
and tested the logic (91 checks, fake audio and fake Claude history). Your local jarvis.py has
hardware tuning the repo copy does not (6x gain, Scarlett device 1, monitor output, 5120x1440 tiling,
scheduled task). Keep all of that. Merge, don't overwrite.

## 1. Copy in two new modules (no edits needed)
- `jarvis_claude.py`: voice control for Claude Code sessions, read only project questions, claude.ai chats.
- `jarvis_room.py`: keep_awake() and start_music() for the walk in scene.

## 2. Wire them into the local jarvis.py (four small edits, see the repo jarvis.py for exact code)
1. `import jarvis_claude, jarvis_room` at the top.
2. In `route()`, right after the "go to sleep" check: `cc = jarvis_claude.route_claude(t); if cc: return cc`.
   Also add `wake up` and `i'm home` to the "open hq" pattern.
3. In `Jarvis.run()`, first line after the unpack: send any action starting with `cc_`, `chat_`, `claude_`
   to `jarvis_claude.ClaudeControl(say, pc, self.claude or find_claude()).handle(action, arg)`.
4. In `main()`, call `jarvis_room.keep_awake()` before loading whisper. In the clap scene (wake_room),
   after the layout, start music on a thread:
   `threading.Thread(target=lambda: jarvis_room.start_music(self.pc, self.spotify, log), daemon=True).start()`.
   The scene must open a FRESH HQ window each time: that load is what wakes HQ on the iPad.

## 3. Windows power (so walk in wake works)
A sleeping PC can't hear. keep_awake() stops sleep while Jarvis runs. Also set it in Windows:
`powercfg /change standby-timeout-ac 0` and `powercfg /change monitor-timeout-ac 10`.
Hibernate stays off. Test: let the monitor turn off, walk out, come back, clap twice.

## 4. Fill in
- `PROJECT_ALIASES` in jarvis_claude.py: nicknames for project folders (auto discovery already finds
  every folder he has used Claude Code in). Print `jarvis_claude.project_index()` and check the names.
- `ROOM_PLAYLIST` in jarvis_room.py: his room playlist link. Exact playlist autostart needs
  SPOTIFY_CLIENT_ID + `--spotify-login` (Premium). Without it, the scene opens Spotify and presses play.

## 5. Find out about Duet
The mission says Claude Duet is installed and runs the 8 AM brief and the check ins every 3 hours.
Find how it can be driven: an exe or CLI (`where duet`, Start menu, %LOCALAPPDATA%), a URL scheme
(registry HKCR), or scheduled tasks. If it has a CLI or URL, add voice commands for "run my brief now"
and "what did Duet say" to the allow list. If it has neither, tell Yash and stop there.

## 6. Live test, in this order
1. "hey jarvis, what was I working on"
2. "hey jarvis, open claude code in jarvis"
3. "hey jarvis, ask jarvis what the clap level is set to"
4. "hey jarvis, new claude chat about college essays" (check that the question is prefilled on claude.ai;
   if claude.ai ignores ?q=, change it to just open a new chat)
5. Monitor off, then double clap: monitor wakes, windows tile, music starts, greeting, iPad HQ wakes.
