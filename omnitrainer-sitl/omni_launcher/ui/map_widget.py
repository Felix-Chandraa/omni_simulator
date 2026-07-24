from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import threading
from typing import Any

from PyQt5.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView

from ..config import LauncherProfile
from ..terrain import fetch_terrain_altitude_m


class MapBridge(QObject):
    location_changed = pyqtSignal(float, float)
    hover_altitude_ready = pyqtSignal(str, float, bool, name="hoverAltitudeReady")

    def __init__(self):
        super().__init__()
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._pending_hover_keys: set[str] = set()
        self._pending_lock = threading.Lock()

    @pyqtSlot(float, float)
    def locationSelected(self, lat: float, lng: float) -> None:
        self.location_changed.emit(float(lat), float(lng))

    @pyqtSlot(float, float, str, name="hoverAltitudeRequested")
    def hoverAltitudeRequested(self, lat: float, lng: float, key: str) -> None:
        key = str(key)
        with self._pending_lock:
            if key in self._pending_hover_keys:
                return
            self._pending_hover_keys.add(key)

        def fetch_hover_altitude() -> None:
            ok = False
            elevation_m = 0.0
            try:
                elevation_m = fetch_terrain_altitude_m(float(lat), float(lng), timeout=4)
                ok = True
            except Exception:
                ok = False
            finally:
                with self._pending_lock:
                    self._pending_hover_keys.discard(key)
                self.hover_altitude_ready.emit(key, elevation_m, ok)

        self._executor.submit(fetch_hover_altitude)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


class MapWidget(QWebEngineView):
    location_changed = pyqtSignal(float, float)

    def __init__(self, profile: LauncherProfile, aviation_data: dict[str, Any], parent=None):
        super().__init__(parent)
        self.profile = profile
        self.aviation_data = aviation_data
        self.bridge = MapBridge()
        self.bridge.location_changed.connect(self.location_changed)
        self.channel = QWebChannel(self)
        self.channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self.channel)
        self.reload(profile, aviation_data)

    def closeEvent(self, event) -> None:
        self.bridge.shutdown()
        super().closeEvent(event)

    def reload(self, profile: LauncherProfile, aviation_data: dict[str, Any]) -> None:
        self.profile = profile
        self.aviation_data = aviation_data
        self.setHtml(build_map_html(profile, aviation_data), QUrl("qrc:///"))

    def set_marker(self, lat: float, lng: float) -> None:
        self.page().runJavaScript(f"if (window.setMarker) window.setMarker({lat:.8f}, {lng:.8f});")

    def set_altitude_unit(self, unit: str) -> None:
        safe_unit = "ft" if unit == "ft" else "m"
        self.page().runJavaScript(f"if (window.setAltitudeUnit) window.setAltitudeUnit({json.dumps(safe_unit)});")


def build_map_html(profile: LauncherProfile, aviation_data: dict[str, Any]) -> str:
    start = profile.start_location
    overlay_json = json.dumps(aviation_data).replace("</", "<\\/")
    start_lat = f"{start.lat:.8f}"
    start_lng = f"{start.lng:.8f}"
    altitude_unit = json.dumps(start.altitude_unit)
    zoom = int(profile.map.default_zoom)
    tile_provider = json.dumps(profile.map.tile_provider)
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Omni Trainer Start Location</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
  <style>
    html, body, #map {{ height: 100%; width: 100%; margin: 0; padding: 0; background: #151515; }}
    .info, .aviation-legend {{
      background: rgba(255,255,255,.96); padding: 8px 10px; border-radius: 6px;
      font-family: Arial, sans-serif; font-size: 12px; line-height: 1.35;
      box-shadow: 0 2px 10px rgba(0,0,0,.25);
    }}
    .legend-title {{ font-weight: bold; margin-bottom: 5px; }}
    .legend-row {{ display: flex; align-items: center; margin-top: 4px; }}
    .legend-airport {{ width: 12px; height: 12px; border: 2px solid #fff; border-radius: 50%; background: #2962ff; margin-right: 8px; }}
    .legend-navaid {{ width: 12px; height: 12px; border: 2px solid #fff; background: #00a676; transform: rotate(45deg); margin-right: 8px; }}
    .legend-radius {{ width: 13px; height: 13px; border: 2px solid #00a676; border-radius: 50%; background: rgba(0,166,118,.14); margin-right: 8px; }}
    .warning {{ margin-top: 7px; padding-top: 6px; border-top: 1px solid #ddd; color: #7a4a00; font-weight: bold; }}
    .airport-label, .air-label {{
      color: white; font-family: Arial, sans-serif; font-size: 11px; font-weight: bold;
      text-shadow: -1px -1px 2px #000, 1px -1px 2px #000, -1px 1px 2px #000, 1px 1px 2px #000;
      white-space: nowrap;
    }}
    .airport-label {{ font-size: 12px; }}
  </style>
</head>
<body>
<div id="map"></div>
<script>
  let bridge = null;
  new QWebChannel(qt.webChannelTransport, function(channel) {{
    bridge = channel.objects.bridge;
    bridge.hoverAltitudeReady.connect(function(key, elevationM, ok) {{
      hoverAltitudeCache.set(key, ok ? elevationM : null);
      if (key === activeHoverKey && activeHoverLat !== null && activeHoverLng !== null) {{
        cursorInfo.update(activeHoverLat, activeHoverLng, ok ? formatAltitude(elevationM) : 'unavailable');
      }}
    }});
  }});

  const startLat = {start_lat};
  const startLng = {start_lng};
  const defaultZoom = {zoom};
  let altitudeUnit = {altitude_unit};
  const preferredTile = {tile_provider};
  const aviationData = {overlay_json};
  const metersToFeet = 3.280839895013123;
  const hoverAltitudeCache = new Map();
  let hoverAltitudeTimer = null;
  let activeHoverKey = null;
  let activeHoverLat = null;
  let activeHoverLng = null;

  const map = L.map('map', {{ preferCanvas: true }}).setView([startLat, startLng], defaultZoom);
  map.createPane('aviationPane'); map.getPane('aviationPane').style.zIndex = 430;
  map.createPane('aviationLabelPane'); map.getPane('aviationLabelPane').style.zIndex = 650;
  map.getPane('aviationLabelPane').style.pointerEvents = 'none';

  const osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
  }});
  const topo = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 17, attribution: 'Map data &copy; OpenStreetMap contributors, SRTM | Map style &copy; OpenTopoMap'
  }});
  const esriImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    maxZoom: 19, attribution: 'Tiles &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community'
  }});
  const esriLabels = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    maxZoom: 19, attribution: 'Labels &copy; Esri'
  }});
  const hybrid = L.layerGroup([esriImagery, esriLabels]);
  const baseLayers = {{ "Satellite Hybrid": hybrid, "Satellite": esriImagery, "Terrain": topo, "Street Map": osm }};
  if (preferredTile === "street") osm.addTo(map);
  else if (preferredTile === "terrain") topo.addTo(map);
  else if (preferredTile === "satellite") esriImagery.addTo(map);
  else hybrid.addTo(map);

  const aviationOverlay = L.layerGroup();
  const airportLayer = L.layerGroup().addTo(aviationOverlay);
  const navaidLayer = L.layerGroup().addTo(aviationOverlay);
  const aviationRadiusLayer = L.layerGroup().addTo(aviationOverlay);
  const airportStyle = {{ pane: 'aviationPane', radius: 6, color: '#fff', weight: 2, fillColor: '#2962ff', fillOpacity: .95 }};
  const navaidStyle = {{ pane: 'aviationPane', radius: 5, color: '#fff', weight: 2, fillColor: '#00a676', fillOpacity: .95 }};

  function htmlEscape(value) {{
    if (value === null || value === undefined) return '';
    return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }}
  function addTextLabel(group, lat, lng, text, className) {{
    const icon = L.divIcon({{ className: className, html: htmlEscape(text), iconSize: null, iconAnchor: [0, 0] }});
    return L.marker([lat, lng], {{ icon: icon, pane: 'aviationLabelPane', interactive: false }}).addTo(group);
  }}
  function addAirport(airport) {{
    const ident = airport.ident || airport.iata || 'AIRPORT';
    const elev = airport.elevation_ft !== null && airport.elevation_ft !== undefined ? airport.elevation_ft + ' ft' : 'N/A';
    const marker = L.circleMarker([airport.lat, airport.lng], airportStyle).addTo(airportLayer);
    marker.bindPopup('<b>' + htmlEscape(ident) + '</b><br>' + htmlEscape(airport.name || '') + '<br>' +
      'Type: ' + htmlEscape(airport.type || 'N/A') + '<br>Municipality: ' + htmlEscape(airport.municipality || 'N/A') +
      '<br>Elevation: ' + htmlEscape(elev) + '<br>Distance: ' + Number(airport.distance_km || 0).toFixed(1) +
      ' km<br><span style="color:#7a4a00;"><b>Verify with official source before flight.</b></span>');
    addTextLabel(airportLayer, airport.lat + 0.006, airport.lng + 0.006, ident, 'airport-label');
  }}
  function addNavaid(navaid) {{
    const ident = navaid.ident || 'NAVAID';
    const freq = navaid.frequency_khz ? navaid.frequency_khz + ' kHz' : 'N/A';
    const marker = L.circleMarker([navaid.lat, navaid.lng], navaidStyle).addTo(navaidLayer);
    marker.bindPopup('<b>' + htmlEscape(ident) + '</b><br>' + htmlEscape(navaid.name || '') + '<br>' +
      'Type: ' + htmlEscape(navaid.type || 'N/A') + '<br>Frequency: ' + htmlEscape(freq) +
      '<br>Distance: ' + Number(navaid.distance_km || 0).toFixed(1) +
      ' km<br><span style="color:#7a4a00;"><b>Verify with official source before flight.</b></span>');
    addTextLabel(navaidLayer, navaid.lat + 0.006, navaid.lng + 0.006, ident, 'air-label');
  }}
  function renderAviationOverlay() {{
    if (!aviationData) return;
    if (aviationData.center) {{
      const radiusMeters = Number(aviationData.center.radius_km || 220) * 1000.0;
      L.circle([aviationData.center.lat, aviationData.center.lng], {{
        pane: 'aviationPane', radius: radiusMeters, color: '#00a676', weight: 2,
        opacity: .65, fillColor: '#00a676', fillOpacity: .03
      }}).addTo(aviationRadiusLayer).bindPopup('<b>Aviation data filter radius</b><br>Radius: ' + Number(aviationData.center.radius_km || 0).toFixed(0) + ' km');
    }}
    if (Array.isArray(aviationData.airports)) aviationData.airports.forEach(addAirport);
    if (Array.isArray(aviationData.navaids)) aviationData.navaids.forEach(addNavaid);
  }}
  renderAviationOverlay();
  aviationOverlay.addTo(map);

  L.control.layers(baseLayers, {{
    "Aviation Overlay": aviationOverlay,
    "Airports": airportLayer,
    "Navaids": navaidLayer,
    "Aviation Filter Radius": aviationRadiusLayer
  }}, {{ collapsed: false }}).addTo(map);

  const legend = L.control({{ position: 'bottomright' }});
  legend.onAdd = function() {{
    const div = L.DomUtil.create('div', 'aviation-legend');
    const airportCount = aviationData && aviationData.airports ? aviationData.airports.length : 0;
    const navaidCount = aviationData && aviationData.navaids ? aviationData.navaids.length : 0;
    const source = aviationData && aviationData.source ? aviationData.source : 'OurAirports';
    div.innerHTML = '<div class="legend-title">Aviation Overlay</div>' +
      '<div class="legend-row"><div class="legend-airport"></div><div>Airports: ' + airportCount + '</div></div>' +
      '<div class="legend-row"><div class="legend-navaid"></div><div>Navaids: ' + navaidCount + '</div></div>' +
      '<div class="legend-row"><div class="legend-radius"></div><div>Overlay filter radius</div></div>' +
      '<div style="margin-top:7px;">Source: ' + htmlEscape(source) + '</div>' +
      '<div class="warning">For simulation only.</div>';
    return div;
  }};
  legend.addTo(map);

  let marker = L.marker([startLat, startLng], {{ draggable: true }}).addTo(map);
  const info = L.control({{ position: 'bottomleft' }});
  info.onAdd = function() {{ this._div = L.DomUtil.create('div', 'info'); this.update(startLat, startLng); return this._div; }};
  info.update = function(lat, lng) {{
    const airportCount = aviationData && aviationData.airports ? aviationData.airports.length : 0;
    const navaidCount = aviationData && aviationData.navaids ? aviationData.navaids.length : 0;
    this._div.innerHTML = '<b>Simulation start point</b><br>Lat: ' + lat.toFixed(7) +
      '<br>Lng: ' + lng.toFixed(7) + '<br>Click map or drag marker.<br><br><b>Aviation data:</b><br>' +
      airportCount + ' airports, ' + navaidCount + ' navaids';
  }};
  info.addTo(map);

  const cursorInfo = L.control({{ position: 'bottomleft' }});
  cursorInfo.onAdd = function() {{
    this._div = L.DomUtil.create('div', 'info');
    this.update(null, null, 'Move cursor over map');
    return this._div;
  }};
  cursorInfo.update = function(lat, lng, altitudeText) {{
    if (lat === null || lng === null) {{
      this._div.innerHTML = '<b>Cursor position</b><br>' + htmlEscape(altitudeText || 'Move cursor over map');
      return;
    }}
    this._div.innerHTML = '<b>Cursor position</b><br>Lng: ' + lng.toFixed(7) +
      '<br>Lat: ' + lat.toFixed(7) + '<br>Altitude: ' + htmlEscape(altitudeText || 'loading...');
  }};
  cursorInfo.addTo(map);

  function formatAltitude(elevationM) {{
    if (elevationM === null || elevationM === undefined || Number.isNaN(Number(elevationM))) return 'unavailable';
    if (altitudeUnit === 'ft') return (Number(elevationM) * metersToFeet).toFixed(1) + ' ft';
    return Number(elevationM).toFixed(1) + ' m';
  }}

  function hoverCacheKey(lat, lng) {{
    return lat.toFixed(4) + ',' + lng.toFixed(4);
  }}

  function requestHoverAltitude(lat, lng) {{
    const key = hoverCacheKey(lat, lng);
    activeHoverKey = key;
    activeHoverLat = lat;
    activeHoverLng = lng;
    if (hoverAltitudeCache.has(key)) {{
      cursorInfo.update(lat, lng, formatAltitude(hoverAltitudeCache.get(key)));
      return;
    }}
    cursorInfo.update(lat, lng, 'loading...');
    if (hoverAltitudeTimer) clearTimeout(hoverAltitudeTimer);
    hoverAltitudeTimer = setTimeout(function() {{
      if (bridge) bridge.hoverAltitudeRequested(lat, lng, key);
      else cursorInfo.update(lat, lng, 'unavailable');
    }}, 450);
  }}

  map.on('mousemove', function(e) {{
    cursorInfo.update(e.latlng.lat, e.latlng.lng, 'loading...');
    requestHoverAltitude(e.latlng.lat, e.latlng.lng);
  }});
  map.on('mouseout', function() {{
    activeHoverKey = null;
    activeHoverLat = null;
    activeHoverLng = null;
    cursorInfo.update(null, null, 'Move cursor over map');
  }});

  function notifyPython(latlng) {{
    marker.setLatLng(latlng); info.update(latlng.lat, latlng.lng);
    if (bridge) bridge.locationSelected(latlng.lat, latlng.lng);
  }}
  map.on('click', function(e) {{ notifyPython(e.latlng); }});
  marker.on('dragend', function() {{ notifyPython(marker.getLatLng()); }});
  window.setMarker = function(lat, lng) {{
    const ll = L.latLng(lat, lng);
    marker.setLatLng(ll); map.setView(ll, map.getZoom()); info.update(lat, lng);
  }};
  window.setAltitudeUnit = function(unit) {{
    altitudeUnit = unit === 'ft' ? 'ft' : 'm';
  }};
</script>
</body>
</html>"""
