Nerds Portal v0.8 for Luci OS

VERSION CHECK
Open Nerds Portal > Network tab. It must show:
  Nerds Portal v0.8
The app name/title must also show Nerds Portal v0.8.

INSTALL ON EACH LUCI PC
Copy only this file into:
  Vinx-Desktop\programfiles\

  nerdsPortal.vx

Do NOT overwrite stable app.vx on Legion.

NO BASE SYSTEM CHANGES
This app does not require editing luci.py, app.vx, .bat files, venv, Render,
or any central relay.

NORMAL TEST FLOW
1. Open Nerds Portal.
2. Create Nerd ID.
3. Press Go Online.
4. Open Inbox / Chat.
5. Type another online user's short +153 number, example +153123456.
6. Send.

The port is automatic. The user should not type ports or raw URLs.
Spaces are accepted, so +153 075561 becomes +153075561.
Both PCs must use this updated nerdsPortal.vx, then reopen the app and press
Go Online again so the LAN discovery listener starts with the new version.
Incoming messages appear in Inbox / Chat and auto-refresh every second.

INTERNATIONAL MODE
Nerds Portal v0.8 adds Nerds Gate support.

Run the public Gate on a VPS:
  python nerds_gate.py --host 0.0.0.0 --port 15300

Or deploy Nerds Gate on GitHub + Render:
  Upload nerds_gate.py and render.yaml to GitHub.
  See RENDER_DEPLOY.txt.

In Nerds Portal > Network:
  Mode: Internet Mode or Hybrid Auto Mode
  Gate URL: ws://PUBLIC_SERVER_IP:15300/ws
  Press Connect Gate

Both users connect outbound to the same Gate. No LAN, no ngrok, no per-user
router port forwarding is required for chat relay.

Production can run the same Gate behind HTTPS/WSS on port 443:
  wss://gate.yourdomain.com/ws

Render gives an HTTPS domain automatically, so use:
  wss://YOUR-SERVICE.onrender.com/ws

LIVE TESTS
Open the Live tab:
  - Check Online: verifies a +153 number is reachable.
  - Rooms: pulls the target user's room list.
  - Feed: pulls the target user's mini feed.
  - Files: pulls file-drop metadata, not file contents yet.
  - Start Snapshot Share: explicitly shares low-res screen snapshots.
  - View Target Snapshot: views the target's current shared snapshot.

CONTACT CARD
Contact Card is only a fallback if auto discovery is not available.

SHORT NUMBERS
Nerds Numbers are now +153 plus 6 digits. If an older long number exists,
press Go Online and the app will auto-migrate that identity to a short number.

LAN DISCOVERY
Go Online announces this app on the LAN and uses a predictable internal port
based on the +153 number. If broadcast discovery fails, the app scans the
local subnet for the matching number.
The Network tab now shows the detected LAN IPs, HTTP port, and discovery
status so you can see whether the app is actually listening.

FOR INTERNATIONAL ACCESS
Use Nerds Gate. The Gate relays by +153 number while each Nerds Portal keeps
its own local identity/device key. The Gate routes; clients own identity.
