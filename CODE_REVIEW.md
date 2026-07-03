# Crosswalk V2 — Code Review Findings (2026-06-11)

The following is a whole-codebase review. Items are ordered by severity. Line
references are to the state of the tree at review time.

### High severity

1. **The web API's ZMQ `REQ` socket gets permanently wedged after a timeout or
   under concurrency** — `xwalk2/api.py`. `APIController` holds a single
   `zmq.REQ` socket (`self.api_socket`) shared by every FastAPI request. `REQ`
   requires strict `send` → `recv` alternation. In `_send_request`, when
   `poll(timeout=5000)` times out the code raises `TimeoutError` *without* doing
   the `recv` — the socket is now stuck in the "awaiting reply" state and the
   very next `send_string` raises `zmq.ZMQError: Operation cannot be accomplished
   in current state`, breaking the API until the process is restarted.
   Additionally, FastAPI handlers are `async` but call this blocking socket
   directly; two overlapping requests interleave `send`/`recv` on the one socket
   and corrupt the same state machine. *Fix:* recreate the socket on timeout/
   error, serialize access with a lock, use a fresh socket per request, or switch
   to `DEALER`/`REQ_RELAXED+REQ_CORRELATE`.

2. **An invalid queued walk name wedges the controller FSM** — `xwalk2/fsm.py`
   `on_enter_walk` + `xwalk2/controller.py` `handle_api_request`. `APIQueueWalk`
   is accepted and appended to `walk_queue` with no validation. When that walk is
   popped, `select_animation_sequence` → `get_audio_duration` raises
   `RuntimeError` if no audio file matches. Because this happens *inside* the
   `transitions` `on_enter_walk` callback, the machine is already in `walk`, no
   `PlayScene` is emitted, and no scene timer is started — so the sign is stuck in
   `walk` (further button presses are invalid from `walk`) until a manual reset.
   *Fix:* validate the walk name against `animations.config` before queuing, and/
   or guard `on_enter_walk` so failures fall back to a normal random walk.

3. **A single missing audio/image asset crashes the component** —
   `xwalk2/audio_player.py` (`self.audio[animation]`), `xwalk2/matrix_driver.py`
   (`self.animations[animation]`). `FileLibrary.__getitem__` raises `KeyError` for
   an unknown name. `SubscribeComponent.run` (`xwalk2/util.py`) has no per-message
   `try/except`, so the exception unwinds the receive loop and the component
   exits. systemd restarts it, but a persistently bad name in a scene yields a
   crash loop. *Fix:* wrap `process_message` in `run`, or look up assets
   defensively and log+skip.

### Medium severity

4. **`tags: -initial` is malformed YAML** — `ansible/roles/crosswalk/tasks/main.yml`.
   `\n    -initial` (no space after the dash) is parsed as the *scalar string*
   `"-initial"`, not a one-element list `["initial"]`. The other imports use the
   correct `- code` form. Result: the initial-setup tasks are tagged literally
   `-initial`, so `--tags initial` never selects them. *Fix:* `- initial`.

5. **Wi-Fi fallback only ever checks once, at boot, and races the network** —
   `ansible/roles/crosswalk/tasks/ap.yml`. `wifi-fallback.service` is a `oneshot`
   pulled in by `multi-user.target`; nothing re-runs it. So if the primary SSID
   (`corginia`) drops *after* boot, the fallback AP is never raised. Worse, it
   runs `After=network-online.target` but Wi-Fi may not have associated yet, so
   the check frequently sees "not connected" and starts the AP even when the
   primary would have come up. *Fix:* drive it from a `systemd timer` or a
   NetworkManager dispatcher script, and add a grace/retry before declaring the
   primary down.

6. **`led-image-viewer` exec-mode `-l 1` is passed as a single argv token** —
   `xwalk2/matrix_driver.py` `_display_command`. `args.append("-l 1")` becomes one
   argument `"-l 1"` (with the embedded space) when `shell=False`, which the
   viewer won't parse. This is currently latent only because `play()` always uses
   `forever=True` and `play_all()` always uses `shell=True` — the broken path is
   never exercised. *Fix:* append `"-l"` and `"1"` as two separate args for the
   non-shell case.

7. **`XWALK_LED_ANGLE` unset yields `Rotate:None`** — `xwalk2/matrix_driver.py`
   `ROTATION = os.getenv("XWALK_LED_ANGLE")`. The systemd unit sets it, but any
   local/manual run without the env var builds `--led-pixel-mapper=U-mapper;Rotate:None`
   and fails confusingly. *Fix:* default it (e.g. `os.getenv("XWALK_LED_ANGLE", "90")`).

8. **`make_stream.sh` destructive/unquoted cleanup with no idempotency** —
   `bin/make_stream.sh` line `rm -rf $OUTPUT_DIR/*` is unquoted (word-splits on
   spaces) and wipes the live `/opt/crosswalk_stream` *before* regenerating, so a
   running matrix driver can read a half-empty directory during the rebuild. The
   ansible task that calls it (`ansible/roles/crosswalk/tasks/code.yml`,
   "Make streams from gifs") has no `creates`/`changed_when`, so it re-runs and
   reports "changed" on every play. *Fix:* quote the path, build into a temp dir
   and atomically swap, and gate the task on changes.

### Low severity / nits

9. **Redundant / fragile lookups in `select_animation_sequence`** —
   `xwalk2/animation_library.py` calls `self.config.get_walk(walk)` up to four
   times and recomputes `audio_walk` twice (lines ~234-249). `get_walk(walk).audio`
   would `AttributeError` if unguarded; it happens to be guarded, but the duplication
   invites a future bug. Compute `walk_info` once and reuse.

10. **README references files that don't exist** — the "Project Structure" list
    above cites `animation.py` and `button_lights.py`; the actual modules are
    `animation_library.py`, `button_light.py`/`button_switch.py` (and the `_virtual`
    variants).

11. **Unused / inconsistent `SystemStatus` model** — `xwalk2/api.py` defines
    `SystemStatus` with `components: Dict[str, float]`, but responses actually use
    `APIResponse` with `components: Dict[str, datetime]`. The unused model is dead
    code with a contradictory type.

12. **Misc:** class name typo `Heatbeat` (should be `Heartbeat`) in
    `xwalk2/models.py`; `Heartbeat.stop()` in `util.py` uses `thread.join(0)` with a
    non-daemon thread (the join is effectively a no-op — it relies on `stop_event`);
    `audio_player` never explicitly stops playback on `EndScene`/`ResetCommand`
    (only the matrix and button-light components react); `sound.yml` hard-codes ALSA
    card index `-c 1` while `asound.conf` selects card `Device`; `test/data/test_anim.py`
    has no assertions (prints only); spelling: `vaild_weights`, "led-iamge-viewer".