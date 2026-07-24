# Feather Flight GCS (Rev 0.020626)

Simple 3D Ground Control Station map using 3D Visualization

Python backend & HTML/CSS/JS frontend
1. Python Backend
   - Talks to the drone/autopilot
   - Handles MAVLink
   - Receives telemetry
   - Sends commands
   - Uploads/downloads missions
   - Exposes data through WebSocket or HTTP API

2. HTML/CSS/JavaScript Frontend
   - Runs in the browser
   - Shows the 3D Cesium map
   - Displays telemetry
   - Shows aircraft position
   - Shows mission waypoints
   - Provides buttons and controls
   - Connects to the Python backend for live data
---
## Dependency
Setup environment:
Windows:
```text
python -m venv build_env
build_env\Scripts\activate
```
Linux:
```text
python3 -m venv build_env
source build_env/bin/activate
```
pip install pyinstaller PyQt6 flask websockets pymavlink PyQt6-WebEngine

---
## Folder Structure

```text
main/
├─ map.html
├─ main.py
├─ config.py
└─ src/
   ├─ main_window.py
   ├─ mav_worker.py
   ├─ preflight_dialog.py
   ├─ server.py
   ├─ css/
   │  ├─ variables.css
   │  ├─ base.css
   │  ├─ layout.css
   │  ├─ panels.css
   │  ├─ controls.css
   │  ├─ gauges.css
   │  ├─ loading.css
   │  └─ responsive.css
   └─ js/
      ├─ main.js
      ├─ config.js
      ├─ state.js
      ├─ dom.js
      ├─ core/
      │  ├─ map.js
      │  ├─ terrain.js
      │  ├─ camera.js
      │  ├─ home.js
      │  └─ aircraft.js
      ├─ mission/ 
      │  ├─ mission.js
      │  ├─ upload.js (future use)
      │  ├─ download.js
      │  └─ validation.js
      ├─ telemetry/
      │  └─ telemetry.js
      ├─ widgets/
      │  ├─ hud.js
      │  ├─ preflight.js
      │  ├─ attitudeIndicator.js (future use) 
      │  ├─ headingTape.js (future use)
      │  └─ altitudeTape.js (future use)
      ├─ mavlink/
      │  ├─ parser.js (partly future use)
      │  ├─ messages.js
      │  └─ websocket.js
      └─ utils/
         ├─ format.js
         ├─ math.js
         └─ events.js (future use)
```

---

## Main File

### `map.html`

This is the main page of the project.

It contains:

- CesiumJS import
- CSS imports
- map container
- telemetry panels
- control buttons
- loading screen
- JavaScript entry file

The JavaScript starts from:

```text
src/js/main.js
```

---

## CSS Files

### `src/css/variables.css`

Stores main CSS variables.

Use it for:

- colors
- borders
- shadows
- radius
- shared theme values

---

### `src/css/base.css`

Basic page setup.

Use it for:

- body style
- font
- full screen layout
- default reset styles

---

### `src/css/layout.css`

Controls the main layout.

Use it for:

- map position
- HUD position
- left panel
- right panel
- bottom bar
- top bar

---

### `src/css/panels.css`

Styles the UI panels.

Use it for:

- telemetry cards
- status boxes
- brand box
- armed/disarmed label

---

### `src/css/controls.css`

Styles buttons and controls.

Use it for:

- Follow Camera button
- Go Home button
- Top View button
- hover styles
- active button styles

---

### `src/css/gauges.css`

Styles compass and altitude display.

Use it for:

- compass circle
- heading value
- altitude card

Future use:

- artificial horizon
- more flight instruments

---

### `src/css/loading.css`

Styles loading and toast messages.

Use it for:

- loading overlay
- loading progress bar
- popup/toast messages

---

### `src/css/responsive.css`

Mobile and small screen fixes.

Use it for:

- phone layout
- tablet layout
- smaller panels

---

## JavaScript Files

### `src/js/main.js`

Main entry point.

It starts the app and connects all modules.

It also exposes functions to the browser window, like:

```text
updateHUD()
setVehiclePosition()
setMissionPath()
setHomePosition()
uploadMission()
downloadMission()
connectMavlinkWebSocket()
```

---

### `src/js/config.js`

Stores project settings.

Use it for:

- Cesium token
- default home location
- camera settings
- aircraft model path
- trail settings

This keeps settings in one place.

---

### `src/js/state.js`

Stores shared app state.

Use it for:

- current telemetry
- Cesium viewer
- aircraft entity
- home position
- mission path
- camera mode

This helps modules share data.

---

### `src/js/dom.js`

Stores HTML element references.

Instead of using `document.getElementById()` everywhere, the elements are saved here.

This keeps the code cleaner.

---

## Core Files

### `src/js/core/map.js`

Creates and sets up the Cesium map.

It handles:

- Cesium Viewer
- terrain
- map startup
- initial camera position

---

### `src/js/core/terrain.js`

Handles terrain height.

Use it for:

- getting ground altitude
- setting home height
- terrain-related altitude checks

---

### `src/js/core/camera.js`

Controls camera movement.

It handles:

- Follow Camera
- Free Camera
- Go Home
- Top View

Future use:

- chase camera
- orbit camera
- mission overview camera

---

### `src/js/core/home.js`

Controls home position.

It handles:

- setting home point
- updating home marker
- using home data from telemetry

Future use:

- click map to set home
- update home from MAVLink
- save home to backend

---

### `src/js/core/aircraft.js`

Controls the aircraft on the map.

It handles:

- aircraft model
- fallback aircraft marker
- aircraft movement
- heading/attitude direction
- aircraft trail

Future use:

- change aircraft model
- improve orientation
- add multiple vehicles

---

## Mission Files

### `src/js/mission/mission.js`

Draws mission waypoints and mission path.

It handles:

- waypoint list
- mission line
- waypoint markers
- waypoint order

---

### `src/js/mission/validation.js`

Checks if mission data is valid.

It checks:

- mission is not empty
- latitude is valid
- longitude is valid

Future use:

- altitude limits
- geofence checks
- takeoff/landing checks

---

### `src/js/mission/upload.js`

Placeholder for mission upload.

Right now it can validate and show mission locally.

Future use:

- upload mission to backend
- upload mission to drone
- send mission using MAVLink

---

### `src/js/mission/download.js`

Placeholder for mission download.

Right now it is simple.

Future use:

- download mission from backend
- download mission from drone
- load saved mission file

---

## Telemetry Files

### `src/js/telemetry/telemetry.js`

Handles telemetry updates.

It updates:

- HUD values
- aircraft position
- heading
- altitude
- battery
- GPS/satellite count
- flight mode
- armed status

Example data can include:

```text
lat
lon
alt
heading
roll
pitch
battery
satellites
mode
armed
```

---

## Widget Files

### `src/js/widgets/hud.js`

Updates the main HUD UI.

It handles:

- telemetry text
- status labels
- compass value
- altitude value
- toast messages
- loading screen

---

### `src/js/widgets/preflight.js`

Controls preflight status.

Use it for:

- showing missing checks
- showing if aircraft is ready
- showing preflight complete/incomplete

Future use:

- GPS check
- battery check
- RC check
- mission check
- EKF check

---

### `src/js/widgets/attitudeIndicator.js`

Placeholder for attitude indicator.

Future use:

- artificial horizon
- roll display
- pitch display

---

### `src/js/widgets/headingTape.js`

Placeholder for heading tape.

Future use:

- moving heading tape
- compass direction labels
- target heading marker

---

### `src/js/widgets/altitudeTape.js`

Placeholder for altitude tape.

Future use:

- vertical altitude tape
- target altitude
- climb/descent indicator

---

## MAVLink Files

### `src/js/mavlink/messages.js`

Stores MAVLink message IDs and names.

Future use:

- add more MAVLink message types
- debug MAVLink messages
- convert message ID to readable name

---

### `src/js/mavlink/parser.js`

Placeholder MAVLink parser.

Future use:

- parse more MAVLink messages
- convert MAVLink data into telemetry
- support backend-decoded MAVLink data

---

### `src/js/mavlink/websocket.js`

Handles WebSocket connection.

Use it to receive live telemetry from a backend.

Future use:

- connect to telemetry server
- receive MAVLink JSON
- auto reconnect
- handle connection errors

---

## Utility Files

### `src/js/utils/format.js`

Formatting helper functions.

Use it for:

- numbers
- coordinates
- degrees
- display text

---

### `src/js/utils/math.js`

Math helper functions.

Use it for:

- clamping values
- degrees/radians
- heading normalization
- number checks

---

### `src/js/utils/events.js`

Placeholder event helper.

Future use:

- app event bus
- telemetry update events
- mission update events
- module communication

---

## Placeholder Files

For future features.

Placeholder files:

```text
src/js/mission/upload.js
src/js/mission/download.js
src/js/widgets/attitudeIndicator.js
src/js/widgets/headingTape.js
src/js/widgets/altitudeTape.js
src/js/mavlink/parser.js
src/js/utils/events.js
```

---

## Future Expansion Ideas

Possible next features:

- real telemetry WebSocket
- real MAVLink connection
- mission upload to drone
- mission download from drone
- artificial horizon
- heading tape
- altitude tape
- waypoint editing on map
- geofence drawing
- battery warnings
- GPS warnings
- failsafe warnings
- multiple aircraft support

---

## Packaging
Windows:
```text
pyinstaller --onefile --windowed --name LiteFlightGCS ^
  --add-data "map.html;." ^
  --add-data "config.py;." ^
  --add-data "dist;dist" ^
  --add-data "src;src" ^
  main.py
```

Linux:
```text
pyinstaller --onefile --windowed --name FeatherFlight \
  --add-data "map.html:." \
  --add-data "config.py:." \
  --add-data "dist:dist" \
  --add-data "src/css:src/css" \
  --add-data "src/js:src/js" \
  main.py
```
