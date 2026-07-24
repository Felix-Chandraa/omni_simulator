# Omni Trainer SITL Launcher Operator Tutorial

This tutorial explains how to operate the Omni Trainer SITL Launcher during a simulation session.

It assumes the application and simulation environment are already installed and ready to use.

## 1. Open The Launcher

From the prepared workstation, open the Omni Trainer SITL Launcher.

If launching from the project folder, use:

```bash
./launch.sh
```

Wait until the launcher window appears.

The main window contains:

- A map on the left.
- Configuration panels on the right.
- Start and Stop buttons at the top.
- A log panel at the bottom.

## 2. Understand The User Interface

The launcher is divided into several working areas.

### Header Bar

The header bar is at the top of the window.

It contains:

- **Start**: starts the simulator and enabled telemetry helpers.
- **Stop**: stops the simulator and related helper processes.

Use **Start** only after the session settings have been checked.

Use **Stop** at the end of the session or when the simulator must be stopped safely.

### Map Area

The map is the main visual area on the left side of the window.

Use it to:

- View the selected simulation area.
- Hover over the map to view cursor longitude, latitude, and terrain altitude.
- Click a point to set the start location.
- Drag the marker to adjust the start location.
- View nearby aviation overlay items when available.

When the marker moves, the latitude and longitude fields in **Start Location** update automatically.

### Side Panel

The side panel is on the right side of the window.

It contains the controls used to prepare the simulation session:

- **Start Location**
- **Aircraft Profile**
- **SITL Options**
- **EFI Options**
- **Rangefinder Options**
- **Aviation Overlay**
- **Process Status**

The side-panel sections are collapsible. At startup, **Start Location** is open at the top and the other section bodies are closed. Click a section header to open or close it.

Work from top to bottom when preparing a normal session.

### Log Panel

The log panel is at the bottom of the window.

It shows:

- validation results
- terrain lookup messages
- SITL startup messages
- EFI and rangefinder messages
- warnings and errors

Check the log panel during startup and whenever a process status changes unexpectedly.

### Process Status Panel

The **Process Status** panel shows the state of each launched process.

Common states include:

- **STOPPED**: the process is not running.
- **STARTING**: the launcher is starting the process.
- **WAITING**: the launcher is waiting for SITL telemetry before starting helpers.
- **RUNNING**: the process is active.
- **CRASHED**: the process failed or exited unexpectedly.

During a normal run, SITL should become **RUNNING**. EFI and Rangefinder should also become **RUNNING** when they are enabled.

## 3. Confirm The Aircraft Profile

In the **Aircraft Profile** panel, confirm that the correct aircraft profile is loaded.

The default profile is:

```text
profiles/omni_trainer_dle30_15kg.yaml
```

Check the displayed aircraft, frame, geometry, and engine information.

If a different profile is required, click **Load Profile** and select the correct profile file.

## 4. Validate The Session

Click **Validate Setup** before starting the simulator.

Validation checks whether the launcher can access the files and runtime components needed for the current session.

If validation passes, continue.

If validation fails, do not start the simulator. Report or resolve the listed issue according to your operating procedure.

## 5. Select The Start Location

Use the **Start Location** panel and the map to set the simulated aircraft starting position.

You can set the location in either of these ways:

- Click on the map.
- Drag the map marker.
- Type latitude and longitude manually.

Confirm these fields:

- **Name**: start location name.
- **Latitude**: start latitude.
- **Longitude**: start longitude.
- **Heading, deg**: aircraft starting direction.

## 6. Set Altitude Unit

Use **Altitude unit** to choose how altitude is shown in the launcher.

Available modes:

- `m`: meters
- `ft`: feet

Changing the unit converts the displayed altitude and offset values.

The simulator receives the correct internal value automatically.

## 7. Set Home Altitude

Set **Home alt MSL** to the aircraft home altitude above mean sea level.

You can enter this value manually in the selected altitude unit.

Example:

- If **Altitude unit** is `m`, enter altitude in meters.
- If **Altitude unit** is `ft`, enter altitude in feet.

## 8. Use Terrain Altitude Lookup

To fill home altitude from terrain data:

1. Select the start location on the map.
2. Choose the altitude unit.
3. Enter **Alt offset** if the home altitude should be above or below terrain elevation.
4. Click **Fetch Terrain Altitude**.

The launcher calculates:

```text
Home altitude = terrain elevation + altitude offset
```

The result is displayed in the selected unit.

If terrain lookup is unavailable, enter **Home alt MSL** manually.

## 9. Confirm SITL Options

In **SITL Options**, confirm the session settings.

Common fields:

- **ArduPilot root**: selected ArduPilot environment.
- **Console**: opens the MAVProxy console.
- **MAVProxy map**: opens the MAVProxy map.
- **Reset params**: resets stored SITL parameters for a clean run.
- **Docker SITL**: runs SITL in Docker when enabled.
- **GCS out**: telemetry output for the ground control station.

For a normal session, keep the approved default values unless the operating procedure requires a change.

## 10. Confirm EFI Options

In **EFI Options**, confirm whether simulated engine telemetry should be active.

Common fields:

- **EFI injector**: enables or disables simulated EFI telemetry.
- **Connect**: telemetry connection used by the injector.
- **QGC mirror**: optional mirror output to the ground control station.
- **Rate Hz**: message rate.
- **Print Hz**: log print rate.

For normal use, leave EFI enabled if engine telemetry is required for the session.

## 11. Confirm Rangefinder Options

In **Rangefinder Options**, confirm whether simulated terrain rangefinder telemetry should be active.

Common fields:

- **Terrain rangefinder**: enables or disables rangefinder telemetry.
- **Rate Hz**: message rate.
- **Print Hz**: log print rate.
- **Min cm**: minimum reported distance.
- **Max cm**: maximum reported distance.

For normal use, keep the approved default values.

## 12. Refresh Aviation Overlay

The map can show nearby airports and navigation aids.

To update this information, click **Refresh Aviation Overlay**.

If updated data is unavailable, the launcher may continue using cached overlay data.

The aviation overlay is an operating reference for the simulator map. It is not used as an authoritative flight information source.

## 13. Start The Simulation

When the profile, start location, altitude, and options are correct, click **Start**.

The launcher then performs the session start sequence:

1. Reads the values from the launcher window.
2. Converts altitude internally if feet mode is selected.
3. Writes the selected start location for ArduPilot.
4. Starts ArduPlane SITL.
5. Waits for the SITL telemetry port.
6. Starts EFI telemetry if enabled.
7. Starts rangefinder telemetry if enabled.

Watch the **Logs** panel during startup.

Wait until the process status panel shows the expected running states.

## 14. Connect The Ground Control Station

Open the approved ground control station application.

Use the configured telemetry output. The default is:

```text
udp:127.0.0.1:14550
```

Confirm that the simulated aircraft is visible and receiving telemetry.

## 15. Monitor The Session

During the simulation, monitor:

- **Logs**: startup messages, telemetry messages, and errors.
- **Process Status**: SITL, EFI, and rangefinder state.
- Ground control station telemetry.
- Map position and nearby overlay information.

If a required process shows a failed or stopped state unexpectedly, stop the session and restart according to procedure.

## 16. Stop The Simulation

At the end of the session, click **Stop**.

The launcher stops:

- SITL
- EFI telemetry injector
- rangefinder telemetry injector
- related simulation processes started by the launcher
- Docker SITL container, if Docker mode was used

Wait until the process statuses return to stopped.

## 17. Normal Operating Sequence

Use this sequence for a standard session:

1. Open the launcher.
2. Confirm the aircraft profile.
3. Click **Validate Setup**.
4. Select the start location.
5. Choose altitude unit.
6. Enter or fetch home altitude.
7. Confirm SITL, EFI, and rangefinder options.
8. Refresh aviation overlay if required.
9. Click **Start**.
10. Connect the ground control station.
11. Run the simulation session.
12. Click **Stop** when finished.
